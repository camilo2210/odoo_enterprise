# Part of Odoo. See LICENSE file for full copyright and licensing details.

from freezegun import freeze_time

from odoo.addons.ai.tests.common import TestAICommon

from odoo.tests import HttpCase, tagged
from odoo.tests.common import users


@tagged("post_install", "-at_install")
class TestAIMethods(HttpCase, TestAICommon):
    @freeze_time('2025-01-20 12:34:56')
    @users('user_internal')
    def test_get_direct_response(self):
        """Test the direct-response endpoint and its completion request."""
        agent = self.agent.with_env(self.env).sudo()
        self.env['ai.composer'].sudo().search(
            [('focused_model_id', '=', False), ('interface_key', '=', 'systray_ai_button')]
        ).ai_agent_id = agent.id
        self.authenticate(self.user_internal.login, self.user_internal.login)
        mocked_response = self.mock_text_response("direct response")
        with self.mock_completion_request([mocked_response]) as mock_request:
            res = self.make_jsonrpc_request(
                "/ai/get_direct_response",
                {
                    "interface_key": "systray_ai_button",
                    "prompt": "<p>Test prompt</p>",
                }
            )
        messages = [{
            'role': 'user',
            'content': [{'type': 'text', 'text': '<p>Test prompt</p>'}],
        }]
        mock_request.assert_called_once_with(
            messages,
            agent._get_instructions(),
            self._prepare_default_tools(agent),
            schema=None,
            usage='agent:custom',
        )

        self.assertEqual(res, 'direct response')
