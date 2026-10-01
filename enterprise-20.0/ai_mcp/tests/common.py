# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID

from odoo.addons.ai.tests.common import TestAICommon
from odoo.addons.ai.utils.ai_utils import format_name_to_llm


class TestMcpCommon(TestAICommon):

    def _create_server_action_on_model(self, model_name, action_name=None, use_in_mcp=True, result=None, group_ids=None):
        model_id = self.env['ir.model'].sudo()._get_id(model_name)
        code = f"ai['result'] = {result}" if result else "ai['result'] = 'test action has been executed'"
        tool_name = action_name if action_name else f'MCP Test {model_name}'
        vals = {
            'name': tool_name,
            'ai_tool_name': format_name_to_llm(tool_name),
            'model_id': model_id,
            'state': 'code',
            'use_in_mcp': use_in_mcp,
            'code': code,
        }
        if group_ids:
            vals['group_ids'] = group_ids
        return self.env['ir.actions.server'].sudo().create(vals)

    def _dispatch(self, method, params=None, sudo=False):
        env = self.env(user=SUPERUSER_ID) if sudo else self.env
        return env['ai.mcp.request.dispatcher']._mcp_dispatch(
            {'id': 1, 'method': method, 'params': params or {}}
        )
