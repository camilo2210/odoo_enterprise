# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import requests

from contextlib import contextmanager
from json import dumps
from unittest.mock import patch

from odoo.addons.ai.tests.common import TestAICallbackCommon
from odoo.addons.social_test_full.tests.common import SocialTestFullCase
from odoo.tests import JsonRpcException, new_test_user, RecordCapturer
from odoo.tools import mute_logger


class TestAiSocialLivechat(TestAICallbackCommon, SocialTestFullCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.facebook_account = cls.accounts.filtered(lambda account: account.media_type == "facebook")[:1]

        cls.operator = new_test_user(
            cls.env,
            "social_livechat_operator",
            groups="im_livechat.im_livechat_group_user",
        )
        cls.env["mail.presence"]._update_presence(cls.operator)
        agent = cls.env.ref("ai_social.ai_social_agent_livechat")
        cls.livechat_channel = cls.env["im_livechat.channel"].create({
            "name": "Facebook AI Livechat",
            "user_ids": cls.operator.ids,
            "ai_social_livechat_agent_id": agent.id,
            "social_away_message": "away message",
        })
        cls.facebook_account.write({
            "facebook_account_id": "facebook-page-1",
            "facebook_access_token": "facebook-token",
            "livechat_channel_id": cls.livechat_channel.id,
        })

    def _send_facebook_webhook(self, facebook_account_id, messaging):
        """Forge the signature like if we received an event from IAP."""
        body = dumps({
            "object": "page",
            "entry": [{
                "id": facebook_account_id,
                "messaging": [messaging],
            }],
        }).encode()
        signature = hmac.new(
            self.env["social.media"]._get_webhook_shared_secret().encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        response = self.url_open(
            "/social_facebook/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Odoo-Signature-256": signature,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self._deliver_iap_callbacks()

    @contextmanager
    def mock_facebook_get(self):
        def _mock_facebook_get(url, params=None, timeout=None):
            if url.endswith("/facebook-user-1"):
                response_json = {"name": "Facebook User"}
            elif url.endswith("/me/conversations"):
                response_json = {
                    "data": [{
                        "id": "conversation-1",
                        "participants": {
                            "data": [
                                {"id": "facebook-page-1"},
                                {"id": "facebook-user-1"},
                            ]
                        },
                    }],
                }
            else:
                assert "/conversation-1/messages" in url
                response_json = {
                    "data": [
                        {
                            "id": "old-message-1",
                            "from": {"id": "123"},
                            "created_time": "2026-07-10T14:30:00+0200",
                            "message": "message"
                        }, {
                            "id": "old-message-2",
                            "from": {"id": "123"},
                            "created_time": "2026-07-10T14:30:00+0200",
                            "message": "message",
                            "reply_to": {"mid": "old-message-1"},
                        },
                    ],
                }

            response = requests.Response()
            response.status_code = 200
            response._content = dumps(response_json).encode()
            response.headers["Content-Type"] = "application/json"
            return response

        with (
            patch("requests.get", side_effect=_mock_facebook_get),
            patch.object(requests.Session, "get", side_effect=_mock_facebook_get),
        ):
            yield

    @contextmanager
    def mock_facebook_post(self):
        self.sent_facebook_messages = []

        def _mock_facebook_post(url, params=None, json=None, timeout=None):
            assert "/me/messages" in url
            self.sent_facebook_messages.append(json)
            response = requests.Response()
            response.status_code = 200
            response._content = dumps(
                {"message_id": f"ai message {len(self.sent_facebook_messages)}"}
            ).encode()
            response.headers["Content-Type"] = "application/json"
            return response

        with patch("requests.post", side_effect=_mock_facebook_post):
            yield

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_ai_social_livechat(self):
        self.assertEqual(self.operator.presence_ids.status, "online")
        agent = self.env.ref("ai_social.ai_social_agent_livechat")
        add_human_tool = self.env.ref("ai_social.ir_actions_server_add_human")
        web_search_tool = self.env.ref("ai.ir_actions_server_ai_web_search")

        llm_responses = [
            self.mock_text_response("test"),
            self.mock_tool_response(add_human_tool),
            self.mock_text_response("Human is coming"),
            self.mock_tool_response(add_human_tool),
            self.mock_text_response("No human operator connected"),
        ]

        with (
            self.mock_callback_completions(llm_responses) as mock_completions,
            self.mock_facebook_get(),
            self.mock_facebook_post(),
        ):
            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "message": {
                        "mid": "message 1",
                        "text": "Hello",
                    },
                },
            )

            guest = self.env["mail.guest"].search([("meta_user_id", "=", "facebook-user-1")])
            self.assertEqual(len(guest), 1)
            self.assertEqual(guest.name, "Facebook User")

            discuss_channel = self.env["discuss.channel"].search(
                [("livechat_social_account_id", "=", self.facebook_account.id)])
            self.assertEqual(len(discuss_channel), 1)
            self.assertEqual(discuss_channel.livechat_customer_guest_ids, guest)
            self.assertEqual(discuss_channel.sudo().ai_agent_id, agent)
            self.assertIn(agent.partner_id, discuss_channel.channel_member_ids.partner_id)

            # check that the history messages have been fetched
            old_messages = self.env["mail.message"].search(
                [("message_id", "in", ("old-message-1", ("old-message-2")))],
                order="id ASC",
            )
            self.assertEqual(len(old_messages), 2)
            self.assertEqual(old_messages[0].message_id, "old-message-2", "First message created should be the oldest one")
            self.assertEqual(old_messages[0].parent_id, old_messages[1], "Should have set the `parent_id` field")

            message_1 = self.env["mail.message"].search([("message_id", "=", "message 1")])
            self.assertEqual(len(message_1), 1)
            self.assertEqual(message_1.author_guest_id, guest)
            self.assertIn("Hello", message_1.body)
            self.assertTrue(message_1.id > max(old_messages.ids), "Should have created the message after the old one")

            self.assertEqual(len(self.sent_facebook_messages), 1)
            self.assertEqual(self.sent_facebook_messages[0]["message"]["text"], "test")

            ai_message = self.env["mail.message"].search([("message_id", "=", "ai message 1")])
            self.assertEqual(len(ai_message), 1)
            self.assertEqual(ai_message.author_id, agent.partner_id)
            self.assertIn("test", ai_message.body)

            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "reaction": {
                        "mid": ai_message.message_id,
                        "action": "react",
                        "emoji": "❤",
                    },
                },
            )
            self.assertEqual(len(self.sent_facebook_messages), 1)
            reaction = self.env["mail.message.reaction"].search(
                [
                    ("message_id", "=", ai_message.id),
                    ("guest_id", "=", guest.id),
                    ("content", "=", "❤"),
                ]
            )
            self.assertTrue(reaction)

            # remove the reaction
            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "reaction": {
                        "mid": ai_message.message_id,
                        "action": "unreact",
                    },
                },
            )
            self.assertFalse(reaction.exists())

            with RecordCapturer(self.env["mail.message"], []) as capture:
                self._send_facebook_webhook(
                    "facebook-page-1",
                    {
                        "sender": {"id": "facebook-user-1"},
                        "recipient": {"id": "facebook-page-1"},
                        "message": {
                            "mid": "message 2",
                            "text": "ask a human",
                        },
                    },
                )
            self.assertEqual(len(self.sent_facebook_messages), 2)
            self.assertEqual(
                self.sent_facebook_messages[1]["message"]["text"],
                "Human is coming",
                "Should have sent the message on Facebook",
            )

            self.assertEqual(len(capture.records), 4)
            self.assertEqual(capture.records[0].message_id, "message 2")
            self.assertEqual(capture.records[1].message_type, "notification")
            self.assertIn("channel-joined", capture.records[1].body)
            self.assertEqual(capture.records[2].message_type, "notification")
            self.assertEqual(capture.records[2].subtype_id, self.env.ref("mail.mt_note"))
            self.assertIn("o-ai-tool-summary", capture.records[2].body)
            self.assertIn(add_human_tool.name, capture.records[2].body)
            self.assertEqual(capture.records[3].message_id, "ai message 2")

            self.assertIn(
                self.operator.partner_id,
                discuss_channel.channel_member_ids.partner_id,
                "Should have added the human in the channel",
            )
            self.assertNotIn(
                agent.partner_id,
                discuss_channel.channel_member_ids.partner_id,
                "The AI agent should be removed from the channel",
            )
            ai_sessions = (
                self.env["ai.session"]
                .with_context(active_test=False)
                .search([("channel_id", "=", discuss_channel.id)])
            )
            self.assertEqual(discuss_channel.livechat_status, "in_progress")
            self.assertEqual(discuss_channel.livechat_failure, "no_answer")
            self.assertEqual(len(ai_sessions), 1)
            discuss_channel.with_user(self.operator)._close_livechat_session("")
            self.assertTrue(discuss_channel.livechat_end_dt)
            self.assertFalse(ai_sessions.active)

            # some time later, the Facebook user sends a new message
            self.operator.presence_ids.status = "offline"
            self.assertFalse(self.livechat_channel.available_operator_ids)
            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "message": {
                        "mid": "message 3",
                        "text": "ask a human again",
                        "reply_to": {"mid": ai_message.message_id},
                    },
                },
            )
            self.assertEqual(len(self.sent_facebook_messages), 3)
            self.assertEqual(
                self.sent_facebook_messages[2]["message"]["text"],
                "No human operator connected",
            )
            self.assertFalse(discuss_channel.livechat_end_dt)
            self.assertEqual(discuss_channel.livechat_status, "need_help")
            self.assertEqual(discuss_channel.livechat_failure, "no_agent")
            self.assertIn(agent.partner_id, discuss_channel.channel_member_ids.partner_id)
            self.assertIn(guest, discuss_channel.channel_member_ids.guest_id)
            self.assertNotIn(self.operator.partner_id, discuss_channel.channel_member_ids.partner_id)
            self.assertEqual(len(discuss_channel.channel_member_ids), 2)

            self.assertEqual(
                self.env["discuss.channel"].search_count([("livechat_social_account_id", "=", self.facebook_account.id)]),
                1,
                "Should have re-used the previous discuss channel to preserve the mail messages",
            )

            reopened_message = self.env["mail.message"].search(
                [("message_id", "=", "message 3")]
            )
            self.assertEqual(len(reopened_message), 1)
            self.assertEqual(reopened_message.parent_id, ai_message)

            ai_sessions = (
                self.env["ai.session"]
                .with_context(active_test=False)
                .search([("channel_id", "=", discuss_channel.id)])
            )
            self.assertEqual(len(ai_sessions), 2)
            self.assertFalse(ai_sessions[0].active)
            self.assertTrue(ai_sessions[1].active)

            # ensure that for all LLM API calls we just made, we only have the tools to
            # add a human and search the web, no "create / update records" tools
            self.assertEqual(len(mock_completions.call_args_list), 5)
            for call_args in mock_completions.call_args_list:
                payload = call_args.args[2]
                self.assertIn(agent._get_livechat_preprompt(), payload['instructions'])
                tools = payload['tools']
                all_tools = [tool["name"] for tool in tools]
                self.assertEqual(
                    set(all_tools),
                    {add_human_tool.ai_tool_name, web_search_tool.ai_tool_name},
                )

            # the human joins manually the channel
            self.assertIn(agent.partner_id, discuss_channel.channel_member_ids.partner_id)
            self.assertNotIn(self.operator.partner_id, discuss_channel.channel_member_ids.partner_id)

            with RecordCapturer(self.env["mail.message"], []) as capture:
                discuss_channel.with_user(self.operator)._add_members(users=self.operator)

            self.assertEqual(len(capture.records), 1)
            self.assertIn(
                "joined the conversation",
                capture.records.body,
                "Don't notify for the bot leaving the channel",
            )
            self.assertIn(
                self.operator.partner_id,
                discuss_channel.channel_member_ids.partner_id,
            )
            self.assertNotIn(
                agent.partner_id,
                discuss_channel.channel_member_ids.partner_id,
            )
            self.assertFalse(
                discuss_channel.sudo().ai_agent_id,
                "Should be False to hide 'Ask human button' from ai_livechat",
            )

            # should never have sent the away message because the AI bot took over the conversation
            # but if the bot is not used, then we should send the away message
            self.assertFalse(discuss_channel.message_ids.filtered(lambda m: "away message" in m.body))
            discuss_channel.with_user(self.operator)._close_livechat_session("")
            self.livechat_channel.ai_social_livechat_enabled_condition = "only_if_operator"
            llm_calls = mock_completions.call_count
            with RecordCapturer(self.env["mail.message"], []) as capture:
                self._send_facebook_webhook(
                    "facebook-page-1",
                    {
                        "sender": {"id": "facebook-user-1"},
                        "recipient": {"id": "facebook-page-1"},
                        "message": {
                            "mid": "message 4",
                            "text": "anyone here?",
                            "reply_to": {"mid": ai_message.message_id},
                        },
                    },
                )

            self.assertEqual(len(capture.records), 2)
            self.assertEqual(mock_completions.call_count, llm_calls)
            self.assertEqual(len(self.sent_facebook_messages), 4)
            self.assertEqual(self.sent_facebook_messages[-1]["message"]["text"], "away message")
            away_messages = discuss_channel.message_ids.filtered(lambda m: "away message" in m.body)
            self.assertEqual(len(away_messages), 1)

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_ai_social_livechat_message_echo(self):
        """Test that we remove the AI agent when we reply from Facebook."""
        agent = self.env.ref("ai_social.ai_social_agent_livechat")

        def send_echo(message_id, recipient="facebook-user-1"):
            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-page-1"},
                    "recipient": {"id": recipient},
                    "message": {"mid": message_id},
                },
            )

        with (
            self.mock_callback_completions([self.mock_text_response("test")]),
            self.mock_facebook_get(),
            self.mock_facebook_post(),
        ):
            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "message": {
                        "mid": "message 1",
                        "text": "Hello",
                    },
                },
            )
            # echo of the AI agent reply, sent from Odoo: keep the AI agent
            send_echo("ai message 1")

            discuss_channel = self.env["discuss.channel"].search(
                [("livechat_social_account_id", "=", self.facebook_account.id)])
            self.assertEqual(len(discuss_channel), 1)
            self.assertEqual(len(self.sent_facebook_messages), 1)
            self.assertEqual(discuss_channel.sudo().ai_agent_id, agent)
            self.assertIn(agent.partner_id, discuss_channel.channel_member_ids.partner_id)

            # echo for an unknown conversation: ignored
            send_echo("ai message 1", recipient="facebook-user-unknown")
            self.assertEqual(discuss_channel.sudo().ai_agent_id, agent)

            # echo of a message we sent from the social media website: remove the AI agent
            ai_session = self.env["ai.session"].with_context(active_test=False).search(
                [("channel_id", "=", discuss_channel.id)])
            self.assertEqual(len(ai_session), 1)
            self.assertTrue(ai_session.active)
            send_echo("Facebook.com message 1")
            self.assertFalse(discuss_channel.sudo().ai_agent_id)
            self.assertNotIn(agent.partner_id, discuss_channel.channel_member_ids.partner_id)
            self.assertFalse(discuss_channel.livechat_end_dt, "Should not close the channel")
            self.assertFalse(ai_session.active)

    @mute_logger("odoo.addons.ai.models.ai_session")
    def test_ai_social_livechat_invited_guest(self):
        """An external guest invited in the discussion can answer on the social media.

        The invited guest is a public user, and so is authenticated with the
        `dgid` cookie instead of being a member of the social groups.
        """
        def post_message(guest, body, auth_cookie=None):
            self.authenticate(None, None)
            self.opener.cookies[guest._cookie_name] = auth_cookie or guest._format_auth_cookie()
            self.make_jsonrpc_request("/mail/message/post", {
                "thread_model": "discuss.channel",
                "thread_id": discuss_channel.id,
                "post_data": {
                    "body": body,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_comment",
                },
            })

        with (
            self.mock_callback_completions([self.mock_text_response("test")]),
            self.mock_facebook_get(),
            self.mock_facebook_post(),
        ):
            self._send_facebook_webhook(
                "facebook-page-1",
                {
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "message": {
                        "mid": "message 1",
                        "text": "Hello",
                    },
                },
            )
            discuss_channel = self.env["discuss.channel"].search(
                [("livechat_social_account_id", "=", self.facebook_account.id)])
            customer_guest = discuss_channel.livechat_customer_guest_ids
            self.assertEqual(len(self.sent_facebook_messages), 1, "Should have sent the AI answer")

            invited_guest = self.env["mail.guest"].create({"name": "Invited Guest"})
            discuss_channel._add_members(guests=invited_guest)
            self.assertNotIn(
                invited_guest,
                discuss_channel.livechat_customer_guest_ids,
                "The invited guest is not the social media customer",
            )

            post_message(invited_guest, "Hello I'm a guest user")
            self.assertEqual(len(self.sent_facebook_messages), 2)
            self.assertEqual(
                self.sent_facebook_messages[1]["message"]["text"],
                "Hello I'm a guest user",
                "Should have sent the message of the invited guest on Facebook",
            )
            self.assertEqual(
                self.sent_facebook_messages[1]["recipient"]["id"],
                "facebook-user-1",
                "Should have sent the message to the social media customer",
            )

            # a guest with an invalid `dgid` cookie can not reach the channel
            with self.assertRaises(JsonRpcException):
                post_message(
                    invited_guest,
                    "Hello I'm not a guest user",
                    auth_cookie=f"{invited_guest.id}|wrong-access-token",
                )
            self.assertEqual(len(self.sent_facebook_messages), 2)

            post_message(customer_guest, "Hello I'm the customer")
            self.assertEqual(
                len(self.sent_facebook_messages),
                2,
                "Should not send back the message of the customer on the social media",
            )

    @mute_logger("odoo.addons.social_facebook.controllers.meta")
    def test_ai_social_livechat_invalid_signature(self):
        body = dumps({
            "object": "page",
            "entry": [{
                "id": "facebook_account_id",
                "messaging": [{
                    "sender": {"id": "facebook-user-1"},
                    "recipient": {"id": "facebook-page-1"},
                    "message": {
                        "mid": "message 1",
                        "text": "Hello",
                    },
                }],
            }],
        }).encode()

        good_secret = self.env["social.media"]._get_webhook_shared_secret().encode()
        for secret, correct in ((good_secret, True), (b"bad secret", False)):
            signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
            response = self.url_open(
                "/social_facebook/webhook",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Odoo-Signature-256": signature,
                },
            )
            self.assertEqual(response.ok, correct)

    @mute_logger("odoo.addons.social_facebook.controllers.meta")
    def test_meta_verify_webhook(self):
        self.env["ir.config_parameter"].set_str("social.facebook_webhook_verify_token", "verify-token")
        valid_params = {
            "hub.challenge": "1234",
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-token",
        }
        response = self.url_open("/social_facebook/webhook", params=valid_params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"1234")

        invalid_params = (
            {**valid_params, "hub.challenge": "not a number"},
            {**valid_params, "hub.mode": "invalid"},
            {**valid_params, "hub.verify_token": "invalid"},
        )
        for params in invalid_params:
            with self.subTest(params=params):
                response = self.url_open("/social_facebook/webhook", params=params)
                self.assertEqual(response.status_code, 403)

        self.env["ir.config_parameter"].set_str("social.facebook_webhook_verify_token", False)
        response = self.url_open("/social_facebook/webhook", params=valid_params)
        self.assertEqual(response.status_code, 403)
