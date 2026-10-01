import json
from unittest.mock import patch

from odoo import Command
from odoo.tests import HttpCase, tagged
from odoo.tools import hmac


@tagged("post_install", "-at_install")
class TestAILivechatCors(HttpCase):

    @patch("odoo.addons.ai.models.ai_session.call_odoo_ai_transport", return_value={})
    def test_cors_start_and_callback_as_guest(self, mock_transport):
        agent = self.env["ai.agent"].create({"name": "Test AI Agent"})
        livechat_channel = self.env["im_livechat.channel"].create({
            "name": "Test AI Livechat Channel",
            "rule_ids": [Command.create({"ai_agent_id": agent.id})],
        })
        session_data = self.make_jsonrpc_request("/im_livechat/cors/get_session", {
            "ai_agent_id": agent.id,
            "channel_id": livechat_channel.id,
            "persisted": True,
        })
        guest_token = session_data["store_data"]["Store"]["guest_token"]
        message_data = self.make_jsonrpc_request("/im_livechat/cors/message/post", {
            "guest_token": guest_token,
            "thread_model": "discuss.channel",
            "thread_id": session_data["channel_id"],
            "post_data": {
                "body": "Hello",
                "message_type": "comment",
                "subtype_xmlid": "mail.mt_comment",
            },
        })

        response = self.url_open(
            "/ai/cors/start_session_advance",
            data=json.dumps({
                "jsonrpc": "2.0",
                "method": "call",
                "id": 0,
                "params": {
                    "guest_token": guest_token,
                    "ai_session_identifier": "livechat-tab",
                    "mail_message_id": message_data["message_id"],
                    "channel_id": session_data["channel_id"],
                    "ai_session_config": {
                        "enable_web_search": True,
                        "enable_resources_only": False,
                        "enable_think_longer": False,
                        "auto_confirm": False,
                    },
                },
            }),
            headers={"Origin": "https://example.com", "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        response_data = response.json()
        self.assertNotIn("error", response_data)
        acknowledgement = response_data["result"]
        self.assertEqual(acknowledgement, {"loop_state": "waiting_model"})

        channel = self.env["discuss.channel"].browse(session_data["channel_id"])
        session = self.env["ai.session"].search([("channel_id", "=", channel.id)])
        guest_id = self.env["mail.guest"]._get_guest_from_token(guest_token).id
        self.assertEqual(session.request_user_id, self.env.ref("base.public_user"))
        self.assertEqual(session.request_guest_id.id, guest_id)
        self.assertEqual(session.loop_state, "waiting_model")
        self.assertEqual(session.request_context["ai_session_identifier"], "livechat-tab")
        mock_transport.assert_called_once()
        self.assertEqual(mock_transport.call_args.args[1], "1/get_completions")
        submitted = mock_transport.call_args.args[2]
        self.assertEqual(submitted["request_uuid"], session.request_uuid)
        self.assertEqual(submitted["webhook_secret"], session.request_webhook_secret)

        command = {"name": "dummy_tool", "params": {"name": "Value"}, "oneway": True}

        def handle_tool_calls(callback_session, *args, **kwargs):
            self.assertTrue(callback_session.env.user._is_public())
            self.assertEqual(callback_session.env.context["guest"].id, guest_id)
            return [
                {"intermediary_message": "Private agent step"},
                {"client_tool": command},
                {
                    "tool_results": [{
                        "tool_call_id": "dummy_call",
                        "tool_name": "dummy_tool",
                        "result": [{"type": "text", "text": "Success"}],
                        "success": True,
                    }],
                    "final_message": [{"type": "text", "text": "Done"}],
                },
            ]

        llm_result = {
            "status": "success",
            "result": {
                "role": "assistant",
                "content": [{
                    "type": "tool_call",
                    "call_id": "dummy_call",
                    "name": "dummy_tool",
                    "args": {"name": "Value", "tool_status": "Thinking"},
                }],
                "provider_metadata": {},
            },
        }
        callback_data = {
            "request_uuid": submitted["request_uuid"],
            "llm_result": llm_result,
            "llm_error": False,
            "signature": hmac(None, "odoo_ai-webhook", (
                submitted["request_uuid"], llm_result, False,
            ), secret=submitted["webhook_secret"]),
        }
        with (
            patch.object(self.env.registry["ai.session"], "_handle_tool_calls", autospec=True, side_effect=handle_tool_calls) as mock_tools,
            patch.object(self.env.registry["discuss.channel"], "_bus_send", autospec=True) as mock_bus_send,
        ):
            # The callback has no guest token; it must restore the saved actor.
            callback_response = self.url_open(
                "/ai/completion_result_ready",
                data=json.dumps(callback_data),
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(callback_response.status_code, 200)
        self.assertIsNone(callback_response.json())
        mock_tools.assert_called_once()
        client_notifications = [
            (notification.args[0].id, notification.args[2])
            for notification in mock_bus_send.call_args_list
            if notification.args[1] == "ai.session/client_tools"
        ]
        self.assertEqual(client_notifications, [
            (channel.id, {"channel_id": channel.id, "commands": [command], "aiSessionIdentifier": "livechat-tab"}),
        ])
        self.assertFalse(any(
            "Private agent step" in str(notification) or "Thinking" in str(notification)
            for notification in mock_bus_send.call_args_list
        ))
        session.invalidate_recordset()
        self.assertEqual(session.loop_state, "ready")
