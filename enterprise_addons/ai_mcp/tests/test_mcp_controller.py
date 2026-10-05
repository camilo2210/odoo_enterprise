# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from datetime import datetime, timedelta

from odoo.tests import HttpCase, tagged, users

from odoo.addons.ai_mcp.tests.common import TestMcpCommon


@tagged('post_install', '-at_install')
class TestMcpController(TestMcpCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        expiration = datetime.now() + timedelta(hours=12)
        cls.user_internal = cls.user_internal.with_user(cls.user_internal)
        cls.mcp_api_key = cls.user_internal.env['res.users.apikeys']._generate('mcp', 'test mcp key', expiration)

    def _mcp_post(self, method, params=None):
        payload = {'id': 1, 'method': method, 'params': params or {}}
        response = self.url_open(
            '/mcp',
            data=json.dumps(payload),
            headers={
                'Authorization': f'Bearer {self.mcp_api_key}',
                'Content-Type': 'application/json',
            },
        )
        return response

    @users('user_internal')
    def test_rollback_on_exception(self):
        channel = self.env['discuss.channel'].create({'name': 'original_name'})
        update_records_action = self.env.ref('ai.ir_actions_server_update_records').sudo()
        update_records_action.use_in_mcp = True
        response = self._mcp_post('tools/call', {
            'name': update_records_action.ai_tool_name,
            'arguments': {
                'explanation': 'partial write rollback test',
                'preview_menus': [],
                'updates': [
                    {
                        'model_name': 'discuss.channel',
                        'domain': f"[('id', '=', {channel.id})]",
                        'changes': [{'field': 'name', 'value': 'SHOULD_BE_ROLLEDBACK'}],
                    },
                    {
                        'model_name': 'discuss.channel',
                        'domain': "[('id', '=', -999999)]",
                        'changes': [{'field': 'name', 'value': 'SHOULD_NOT_APPLY'}],
                    },
                ],
            },
        })
        result = response.json()['result']
        self.assertTrue(result['isError'])
        self.assertIn("No records were found corresponding to the domain '[('id', '=', -999999)]", result['content'][0]['text'])
        self.assertEqual(channel.name, 'original_name')

    @users('user_internal')
    def test_unknown_method_returns_jsonrpc_error(self):
        response = self._mcp_post('server/discover')
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('result', body)
        self.assertEqual(body['id'], 1)
        self.assertEqual(body['error']['code'], -32601)
        self.assertEqual(body['error']['message'], "Method doesn't exist")
        self.assertEqual(body['error']['data']['method'], 'server/discover')
