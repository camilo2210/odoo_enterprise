# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo.addons.ai.tests.common import TestAICommon


class TestAIFieldsCommon(TestAICommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_str('ai.openai_key', 'test-openai-key')

    def mock_ai_field_response(self, value, resolved=True, unresolved_msg=None):
        return self.mock_text_response(json.dumps({
            'value': value,
            'could_not_resolve': not resolved,
            'unresolved_cause': unresolved_msg
        }))
