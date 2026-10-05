# Part of Odoo. See LICENSE file for full copyright and licensing details.
import copy
from collections import deque
from contextlib import contextmanager
from unittest.mock import Mock, patch

from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import hmac

from odoo.addons.ai.models.ai_agent import AIAgent
from odoo.addons.ai.models.ai_embedding import AIEmbedding
from odoo.addons.ai.models.ai_session import AiSession
from odoo.addons.ai.models.ir_actions_server import IrActionsServer
from odoo.addons.ai.utils.ai_utils import UserInputResponse


class TestAICommon(TransactionCase):
    """Common helpers for testing Enterprise against normalized IAP responses."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_internal = cls.env['res.users'].create({
            'name': 'User internal',
            'login': 'user_internal',
            'email': 'user_internal@user.com',
            'group_ids': [Command.set(cls.env.ref('base.group_user').ids)],
        })
        cls.call_id = 0

        cls.agent = cls.env['ai.agent'].create({
            'name': 'Test Agent',
            'system_prompt': "Do this",
        })
        cls.agent_with_sources = cls.env['ai.agent'].create({
            'name': 'Test Agent with sources',
            'system_prompt': "Do this",
        })
        test_attachment = cls.env['ir.attachment'].create({
            'name': 'test_doc.txt',
            'raw': b'Odoo is an open-source ERP system with many modules.',
            'res_model': 'ai.agent',
            'res_id': cls.agent_with_sources.id,
        })
        cls.test_source = cls.env['ai.agent.source'].create({
            'name': 'Test Source',
            'type': 'binary',
            'agent_id': cls.agent_with_sources.id,
            'attachment_id': test_attachment.id,
            'status': 'indexed',
            'is_active': True,
        })
        cls.test_embedding = cls.env['ai.embedding'].create(
        {
            'res_model': 'ir.attachment',
            'res_id': test_attachment.id,
            'content': test_attachment.index_content,
            'embedding_model': 'embedding_model',
            'embedding_vector': [0.1] * 1536,
            'sequence': 1,
        })
        cls.tools = cls.env['ir.actions.server'].create([{
            'model_id': cls.env["ir.model"]._get_id('ai.agent'),
            'state': 'code',
            'name': f'tool_{i + 1}_',
            'ai_tool_name': f'tool_{i + 1}_',
            'use_in_ai': True,
            'code': f"ai['result'] = 'tc_{i + 1}'"
        } for i in range(3)])
        cls.skill_loading_tool = cls.env.ref("ai.ir_actions_server_load_skills")
        cls.skill = cls.env['ai.skill'].create({
            'name': 'Test Skill',
            'instructions': 'Use this when needed',
            'tool_ids': cls.tools.ids,
        })
        cls.agent_with_tools = cls.env['ai.agent'].create({
            'name': 'Test Agent with tools',
            'skill_ids': cls.skill,
        })

    def mock_completion_request(self, responses):
        return patch.object(AiSession, '_get_completions', side_effect=({
            'status': 'success',
            'result': {
                'role': 'assistant',
                'content': parts,
                'provider_metadata': {},
            },
        } for parts in responses))

    def mock_embedding_request(self):
        return patch.object(AIEmbedding, '_get_embeddings', side_effect=lambda self, input, *args, **kwargs: {
            'status': 'success',
            'embeddings': [[0.1] * 1536 for _ in range(len(input))],
        }, autospec=True)

    def mock_default_tools(self, tools: IrActionsServer):
        return patch.object(
            AIAgent, "_get_default_tools", autospec=True,
            side_effect=lambda agent: agent.env["ir.actions.server"].browse(tools.ids),
        )

    def mock_tool_response(self, tool, args=None):
        tool.ensure_one()
        self.call_id += 1
        return [{
            'type': 'tool_call',
            'name': tool.sudo().ai_tool_name,
            'args': args or {},
            'call_id': self.call_id,
        }]

    def mock_text_response(self, text):
        return [{'type': 'text', 'text': text}]

    def _create_ai_session(self, agent: AIAgent):
        return self.env['ai.session'].sudo().create({
            'agent_id': agent.id,
            'channel_id': agent._create_ai_chat_channel().id,
        })

    def _get_ai_session_default_controls(self):
        return {
            "enable_web_search": True,
            "enable_resources_only": False,
            "enable_think_longer": False,
            "auto_confirm": False,
            "show_agent_steps": False,
        }

    def _get_tool_result(self, session, call_id):
        return next(
            part
            for event in session.event_ids
            for part in event.metadata.get('content', [])
            if part.get('type') == 'tool_result'
            and part['tool_call_id'] == call_id
        )

    def _assert_tool_result_texts(self, event, expected):
        self.assertEqual(
            [
                (
                    part['tool_call_id'],
                    part['result'][0].get('text'),
                    part['success'],
                )
                for part in event.metadata.get('content', [])
                if part.get('type') == 'tool_result'
            ],
            expected,
        )

    def _prepare_default_tools(self, agent: AIAgent, session: AiSession = None):
        tools = session._get_session_default_tools() if session else agent._get_default_tools()
        tools_by_name = {tool.sudo().ai_tool_name: tool for tool in tools}
        return self.env["ai.session"]._prepare_tools(tools_by_name)


@tagged("post_install", "-at_install")
class TestAICallbackCommon(HttpCase, TestAICommon):
    """Exercise session endpoints with a fake IAP transport."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))

    def _create_ai_session(self, agent: AIAgent):
        agent = agent.with_env(self.env)
        return self.env["ai.session"].sudo().create({
            "agent_id": agent.id,
            # These tests supply conversation replies, not channel-title replies.
            "channel_id": agent._create_ai_chat_channel("Test conversation").id,
        })

    @contextmanager
    def mock_callback_completions(self, responses, *, channel_name="Test conversation"):
        self._iap_requests = deque()
        self._iap_replies = iter(responses)
        self._iap_channel_name = channel_name
        conversation_transport = Mock()

        def accept_request(connection, route, params, **kwargs):
            self.assertEqual(route, "1/get_completions")
            self._iap_requests.append(copy.deepcopy(params))
            if params["usage"] != "channel_name":
                conversation_transport(connection, route, params, **kwargs)
            return {}

        with patch(
            "odoo.addons.ai.models.ai_session.call_odoo_ai_transport",
            side_effect=accept_request,
        ):
            yield conversation_transport
        self.assertFalse(self._iap_requests)

    def _deliver_iap_callbacks(self):
        while self._iap_requests:
            submitted = self._iap_requests.popleft()
            if submitted["usage"] == "channel_name":
                content = self.mock_text_response(self._iap_channel_name)
            else:
                content = next(self._iap_replies)
            llm_result = {"result": {
                "role": "assistant",
                "content": content,
                "provider_metadata": {},
            }}
            response = self.url_open(
                "/ai/completion_result_ready",
                json={
                    "request_uuid": submitted["request_uuid"],
                    "llm_result": llm_result,
                    "llm_error": False,
                    "signature": hmac(None, "odoo_ai-webhook", (
                        submitted["request_uuid"], llm_result, False,
                    ), secret=submitted["webhook_secret"]),
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIsNone(response.json())
        self.env.invalidate_all()

    def _call_ai_endpoint(self, route, params):
        user = self.env.user
        self.authenticate(user.login, user.login, session_extra={
            "context": {"allowed_company_ids": self.env.companies.ids},
        })
        acknowledgement = self.make_jsonrpc_request(route, params)
        self._deliver_iap_callbacks()
        return acknowledgement

    def _post_user_message_on_session(self, session: AiSession, body: str, ai_session_config=None):
        mail_msg = session.channel_id.message_post(body=body, message_type="comment")
        config = self._get_ai_session_default_controls() | {"ai_prompt_button_ref": None} | (ai_session_config or {})
        return self._call_ai_endpoint("/ai/start_session_advance", {
            "channel_id": session.channel_id.id,
            "mail_message_id": mail_msg.id,
            "ai_session_config": config,
        })

    def _resume_pending_tool_on_session(self, session: AiSession, response, ai_session_config=None):
        return self._call_ai_endpoint("/ai/resume_pending_interaction", {
            "channel_id": session.channel_id.id,
            "session_id": session.id,
            "resume_token": session.resume_token,
            "response": response,
            "ai_session_config": ai_session_config,
        })

    def _confirm_pending_tool(self, session: AiSession, auto_confirm: bool = False):
        return self._resume_pending_tool_on_session(session, {
            "kind": "confirmation",
            "value": UserInputResponse.AUTO_CONFIRM if auto_confirm else UserInputResponse.CONFIRM_ONCE,
        }, ai_session_config=self._get_ai_session_default_controls())


@contextmanager
def mock_iap_results(env, return_values, *, channel_name="test_channel"):
    """Send signed mocked IAP replies to the admin tour over the bus."""
    responses = iter(return_values)

    def submit(connection, route, params, **kwargs):
        assert route == "1/get_completions"
        if params["usage"] == "channel_name":
            content = [{"type": "text", "text": channel_name}]
        else:
            content = next(responses)

        llm_result = {"result": {
            "role": "assistant",
            "content": content,
            "provider_metadata": {},
        }}
        env.ref("base.user_admin")._bus_send("ai.test/callbacks_ready", {
            "request_uuid": params["request_uuid"],
            "llm_result": llm_result,
            "llm_error": False,
            "signature": hmac(None, "odoo_ai-webhook", (
                params["request_uuid"], llm_result, False,
            ), secret=params["webhook_secret"]),
        })
        # Submission is already in postcommit; dispatch this test notification explicitly.
        env.cr.precommit.run()
        env.cr.postcommit.run()
        return {}

    with patch("odoo.addons.ai.models.ai_session.call_odoo_ai_transport", side_effect=submit):
        yield
