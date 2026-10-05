# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo.tests import tagged, users
from odoo.tools import mute_logger
from odoo.exceptions import AccessError

from odoo.addons.ai_mcp.tests.common import TestMcpCommon


@tagged('post_install', '-at_install')
class TestMcpAccess(TestMcpCommon):

    @users('user_internal')
    def test_create_record_on_accessible_model(self):
        create_records_tool = self.env.ref('ai.ir_actions_server_create_records').sudo()
        create_records_tool.use_in_mcp = True
        result = self._dispatch('tools/call', {
            'name': create_records_tool.ai_tool_name,
            'arguments': {
                'explanation': 'Creating a test discuss channel',
                'model_name': 'discuss.channel',
                'values': [{'field_values': [{'field': 'name', 'value': 'Test Discuss Channel'}]}],
            },
        })
        self.assertFalse(result['isError'])
        channel = self.env['discuss.channel'].search([('name', '=', 'Test Discuss Channel')])
        self.assertEqual(len(channel), 1)

    @users('user_internal')
    def test_create_record_on_inaccessible_model(self):
        create_records_tool = self.env.ref('ai.ir_actions_server_create_records').sudo()
        create_records_tool.use_in_mcp = True
        with self.assertRaisesRegex(AccessError, "You are not allowed to create 'AI Session'"):
            self._dispatch('tools/call', {
                'name': create_records_tool.ai_tool_name,
                'arguments': {
                    'explanation': 'Trying to create on restricted model',
                    'model_name': 'ai.session',
                    'values': [{'field_values': [{'field': 'agent_id', 'value': self.agent.id}]}],
                },
            })

    @users('user_internal')
    def test_update_accessible_model_record(self):
        update_records_tool = self.env.ref('ai.ir_actions_server_update_records').sudo()
        update_records_tool.use_in_mcp = True
        channel = self.env['discuss.channel'].create({'name': 'Test Discuss Channel'})
        result = self._dispatch('tools/call', {
            'name': update_records_tool.ai_tool_name,
            'arguments': {
                'explanation': 'Trying to update discuss.channel model',
                'preview_menus': [],
                'updates': [{
                    'model_name': 'discuss.channel',
                    'domain': f"[('id', '=', {channel.id})]",
                    'changes': [{'field': 'name', 'value': 'Updated'}],
                }],
            },
        })
        self.assertFalse(result['isError'])
        self.assertEqual(channel.name, 'Updated')

    @users('user_internal')
    def test_update_inaccessible_model_record(self):
        update_records_tool = self.env.ref('ai.ir_actions_server_update_records').sudo()
        update_records_tool.use_in_mcp = True
        session = self.env['ai.session'].sudo().create({'agent_id': self.agent.id})
        with self.assertRaisesRegex(AccessError, re.escape("You are not allowed to access 'AI Session' (ai.session)")):
            self._dispatch('tools/call', {
                'name': update_records_tool.ai_tool_name,
                'arguments': {
                    'explanation': 'Trying to update restricted model',
                    'preview_menus': [],
                    'updates': [{
                        'model_name': 'ai.session',
                        'domain': f"[('id', '=', {session.id})]",
                        'changes': [{'field': 'state', 'value': '{}'}],
                    }],
                },
            })

    @users('user_internal')
    def test_get_models_includes_only_accessible_models(self):
        tool_name = self.env.ref('ai.ir_actions_server_get_models').sudo().ai_tool_name
        result = self._dispatch('tools/call', {'name': tool_name, 'arguments': {}})
        self.assertFalse(result['isError'])
        models_csv = result['content'][0]['text']
        self.assertIn('res.partner', models_csv)
        self.assertIn('res.partner.category', models_csv)
        self.assertIn('discuss.channel', models_csv)
        self.assertNotIn('ai.session', models_csv)

        sudo_result = self._dispatch('tools/call', {'name': tool_name, 'arguments': {}}, sudo=True)
        self.assertFalse(sudo_result['isError'])
        models_csv = sudo_result['content'][0]['text']
        self.assertIn('res.partner', models_csv)
        self.assertIn('res.partner.category', models_csv)
        self.assertIn('discuss.channel', models_csv)
        self.assertIn('ai.session', models_csv)

    @users('user_internal')
    def test_get_accessible_model_fields(self):
        tool_name = self.env.ref('ai.ir_actions_server_get_fields').sudo().ai_tool_name
        result = self._dispatch('tools/call', {'name': tool_name, 'arguments': {'model_name': 'res.partner'}})
        self.assertFalse(result['isError'])
        self.assertIn('name', result['content'][0]['text'])

    @users('user_internal')
    def test_get_inaccessible_model_fields(self):
        tool_name = self.env.ref('ai.ir_actions_server_get_fields').sudo().ai_tool_name
        with self.assertRaisesRegex(AccessError, re.escape("You are not allowed to access 'AI Session' (ai.session)")):
            self._dispatch('tools/call', {'name': tool_name, 'arguments': {'model_name': 'ai.session'}})

    @users('user_internal')
    def test_get_fields_includes_only_accessible_fields(self):
        tool_name = self.env.ref('ai.ir_actions_server_get_fields').sudo().ai_tool_name
        result = self._dispatch('tools/call', {'name': tool_name, 'arguments': {'model_name': 'discuss.channel'}})
        self.assertFalse(result['isError'])
        fields_csv = result['content'][0]['text']
        self.assertIn('name', fields_csv)
        self.assertNotIn('sfu_channel_uuid', fields_csv)
        self.assertNotIn('sfu_server_url', fields_csv)

        sudo_result = self._dispatch('tools/call', {'name': tool_name, 'arguments': {'model_name': 'discuss.channel'}}, sudo=True)
        self.assertFalse(sudo_result['isError'])
        fields_csv = sudo_result['content'][0]['text']
        self.assertIn('name', fields_csv)
        self.assertIn('sfu_channel_uuid', fields_csv)
        self.assertIn('sfu_server_url', fields_csv)

    @users('user_internal')
    def test_search_on_accessible_model(self):
        self.env['res.partner'].sudo().create({'name': 'name of mcp test partner'})
        tool_name = self.env.ref('ai.ir_actions_server_search').sudo().ai_tool_name
        result = self._dispatch('tools/call', {
            'name': tool_name,
            'arguments': {'model_name': 'res.partner', 'domain': "[('name', '=', 'name of mcp test partner')]", 'fields': ['name']},
        })
        self.assertFalse(result['isError'])
        self.assertIn('name of mcp test partner', result['content'][0]['text'])

    @users('user_internal')
    def test_search_on_inaccessible_model(self):
        tool_name = self.env.ref('ai.ir_actions_server_search').sudo().ai_tool_name
        with self.assertRaisesRegex(ValueError, re.escape("The model 'ai.session' doesn't exist or is inaccessible to the current user")):
            self._dispatch('tools/call', {
                'name': tool_name,
                'arguments': {'model_name': 'ai.session', 'domain': "[]", 'fields': ['id']},
            })

    @users('user_internal')
    def test_read_group_on_accessible_model(self):
        self.env['res.partner'].sudo().create([{'name': 'Alpha'}, {'name': 'Beta'}])
        tool_name = self.env.ref('ai.ir_actions_server_read_group').sudo().ai_tool_name
        result = self._dispatch('tools/call', {
            'name': tool_name,
            'arguments': {'model_name': 'res.partner', 'domain': "[]", 'groupby': ['name']},
        })
        self.assertFalse(result['isError'])
        self.assertIn('Alpha', result['content'][0]['text'])
        self.assertIn('Beta', result['content'][0]['text'])

    @users('user_internal')
    def test_read_group_on_inaccessible_model(self):
        tool_name = self.env.ref('ai.ir_actions_server_read_group').sudo().ai_tool_name
        with self.assertRaisesRegex(ValueError, re.escape("The model 'ai.session' doesn't exist or is inaccessible to the current user")):
            self._dispatch('tools/call', {
                'name': tool_name,
                'arguments': {'model_name': 'ai.session', 'domain': "[]", 'groupby': ['agent_id']},
            })

    @mute_logger('odoo.addons.base.models.ir_actions')
    @users('user_internal')
    def test_only_show_tools_defined_on_accessible_models(self):
        action = self._create_server_action_on_model('ai.session')
        tool_name = action.ai_tool_name
        self.assertNotIn(tool_name, [t['name'] for t in self._dispatch('tools/list')['tools']])
        self.assertIn(tool_name, [t['name'] for t in self._dispatch('tools/list', sudo=True)['tools']])

    @mute_logger('odoo.addons.base.models.ir_actions')
    @users('user_internal')
    def test_server_action_visibility_requires_model_access(self):
        action = self._create_server_action_on_model('ai.session')
        tool_name = action.ai_tool_name

        tool_names = [t['name'] for t in self._dispatch('tools/list')['tools']]
        self.assertNotIn(tool_name, tool_names)

        with self.assertRaises(AccessError):
            self._dispatch('tools/call', {'name': tool_name})

        tool_names_admin = [t['name'] for t in self._dispatch('tools/list', sudo=True)['tools']]
        self.assertIn(tool_name, tool_names_admin)

        result = self._dispatch('tools/call', {'name': tool_name}, sudo=True)
        self.assertFalse(result['isError'])

    @users('user_internal')
    def test_server_action_with_group_ids_requires_group_membership(self):
        # Scenario A: user_internal is in the action's group but has no write access to the model.
        # Group membership overrides model access — user should see and call the tool.
        mcp_test_group = self.env['res.groups'].sudo().create({'name': 'MCP Test Group With User'})
        mcp_test_group.write({'user_ids': [(4, self.env.user.id)]})
        action_group_accessible = self._create_server_action_on_model(
            'ai.session', action_name='MCP Group Accessible Action', group_ids=[(4, mcp_test_group.id)]
        )

        tool_names = [t['name'] for t in self._dispatch('tools/list')['tools']]
        self.assertIn(action_group_accessible.ai_tool_name, tool_names)

        result = self._dispatch('tools/call', {'name': action_group_accessible.ai_tool_name})
        self.assertFalse(result['isError'])

        # Scenario B: user_internal has write access to the model but is NOT in the action's group.
        # Model access alone is not enough — group membership is required.
        group_without_user = self.env['res.groups'].sudo().create({'name': 'MCP Test Group Without User'})
        action_group_restricted = self._create_server_action_on_model(
            'res.partner', action_name='MCP Group Restricted Action', group_ids=[(4, group_without_user.id)]
        )

        tool_names = [t['name'] for t in self._dispatch('tools/list')['tools']]
        self.assertNotIn(action_group_restricted.ai_tool_name, tool_names)

        with self.assertRaises(AccessError):
            self._dispatch('tools/call', {'name': action_group_restricted.ai_tool_name})

    @users('user_internal')
    def test_server_action_tool_in_list_tools_and_callable(self):
        action = self._create_server_action_on_model('res.partner')
        tool_name = action.ai_tool_name
        self.assertIn(tool_name, [t['name'] for t in self._dispatch('tools/list')['tools']])

        result = self._dispatch('tools/call', {'name': tool_name})
        self.assertFalse(result['isError'])
        self.assertIn('test action has been executed', result['content'][0]['text'])
