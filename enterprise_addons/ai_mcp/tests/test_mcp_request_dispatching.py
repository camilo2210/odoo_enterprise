# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from odoo.addons.ai_mcp.tests.common import TestMcpCommon


@tagged('post_install', '-at_install')
class TestMcpRequestDispatching(TestMcpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_tool_xmlid = 'ai.ir_actions_server_create_records'
        cls.update_tool_xmlid = 'ai.ir_actions_server_update_records'

    def test_tools_with_use_in_mcp_are_registered(self):
        mcp_action = self._create_server_action_on_model('res.partner', action_name="mcp_action")
        non_mcp_action = self._create_server_action_on_model('res.partner', action_name="non_mcp_action", use_in_mcp=False)
        mcp_action_tool_name = mcp_action.ai_tool_name
        non_mcp_action_tool_name = non_mcp_action.ai_tool_name

        tool_names = [t['name'] for t in self._dispatch('tools/list')['tools']]
        self.assertIn(mcp_action_tool_name, tool_names)
        self.assertNotIn(non_mcp_action_tool_name, tool_names)

        result = self._dispatch('tools/call', {'name': mcp_action_tool_name})
        self.assertFalse(result['isError'])
        self.assertIn('test action has been executed', result['content'][0]['text'])

        with self.assertRaisesRegex(ValueError, f"The tool '{non_mcp_action_tool_name}' doesn't exist"):
            self._dispatch('tools/call', {'name': non_mcp_action_tool_name})
