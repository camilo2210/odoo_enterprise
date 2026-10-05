# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from markupsafe import Markup

from odoo.addons.ai.tests.common import TestAICommon
from odoo.tests import tagged, users


@tagged("post_install", "-at_install")
class TestAIPromptButton(TestAICommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.composer_id = cls.env['ai.composer'].create({
            'name': 'test composer',
            'interface_key': 'chatter_ai_button',
            'focused_model_id': cls.env.ref('ai.model_ai_agent').id,
        })
        cls.rendering_record = cls.env['ai.agent'].create({
            'name': 'Test record',
        })

    @users('user_internal')
    def test_button_without_prompt(self):
        """
        When the prompt field of the prompt button is empty, the name field is used as the prompt.
        """
        button = self.env['ai.prompt.button'].sudo().create({
            'name': 'Button without prompt',
            'composer_id': self.composer_id.id,
        })
        message_parts = button.sudo(False)._render_prompt(self.rendering_record.id)
        self.assertEqual(message_parts, [{'type': 'text', 'text': 'Button without prompt'}])

        self.composer_id.focused_model_id = self.env.ref('ai.model_ai_agent').id
        button = self.env['ai.prompt.button'].sudo().create({
            'name': 'Button with empty prompt',
            'composer_id': self.composer_id.id,
            'prompt': Markup('<p></p>')
        })
        message_parts = button.sudo(False)._render_prompt(self.rendering_record.id)
        self.assertEqual(message_parts, [{'type': 'text', 'text': 'Button with empty prompt'}])

    @users('user_internal')
    def test_render_basic_prompt(self):
        """
        The prompt field of the button has a value, but it is simple text and doesn't contain any field references.
        """
        self.composer_id.focused_model_id = self.env.ref("ai.model_ai_agent").id
        button = self.env['ai.prompt.button'].sudo().create({
            'name': 'Basic Prompt',
            'prompt': '<p>This is a basic prompt</p>',
            'composer_id': self.composer_id.id,
        })
        message_parts = button.sudo(False)._render_prompt(self.rendering_record.id)
        self.assertEqual(len(message_parts), 1)
        self.assertEqual(message_parts[0]['type'], 'text')
        self.assertIn('This is a basic prompt', message_parts[0]['text'])
        self.assertIn('# field values\n{}', message_parts[0]['text'])

    @users('user_internal')
    def test_render_prompt_with_fields(self):
        """
        The prompt field of the button contains field references.
        """
        self.composer_id.focused_model_id = self.env.ref('ai.model_ai_agent').id
        # Use the specific span format required by parse_ai_prompt_values
        button = self.env['ai.prompt.button'].sudo().create({
            'name': 'Field Prompt',
            'prompt': """
            <div>
                <p>Agent name: <span data-ai-field="name">Name</span></p>
                <p>Agent image: <span data-ai-field="image_128">Image</span></p>
                <p>Partner name: <span data-ai-field="partner_id.name">Partner Name</span></p>
            </div>
            """,
            'composer_id': self.composer_id.id,
        })

        message_parts = button.sudo(False)._render_prompt(self.rendering_record.id)
        self.assertEqual(len(message_parts), 2)

        text_part = message_parts[0]
        rendered_prompt_content = text_part['text']
        self.assertIn('Agent name: {{name}}', rendered_prompt_content)
        self.assertIn('Agent image: {{image_128}}', rendered_prompt_content)
        self.assertIn('Partner name: {{partner_id.name}}', rendered_prompt_content)

        agent_image_checksum = self.env['ir.attachment']._compute_checksum(self.rendering_record.image_128)
        agent_partner_id = self.rendering_record.partner_id.id
        field_values = {
            'ai.agent': [{
                'id': self.rendering_record.id,
                'name': 'Test record',
                'image_128': f'<file_{agent_image_checksum}/>',
                'partner_id': {
                    'model': 'res.partner',
                    'ids': [agent_partner_id]
                }
            }],
            'res.partner': [{
                'id': agent_partner_id,
                'name': 'Test record'
            }]
        }
        prompt_field_values = rendered_prompt_content.split('# field values\n')[1]
        self.assertEqual(field_values, json.loads(prompt_field_values))

        inline_data_part = message_parts[1]
        self.assertEqual(inline_data_part['type'], 'inline_data')
        self.assertEqual(inline_data_part['mimetype'], 'image/png')
        self.assertEqual(inline_data_part['data'], self.rendering_record.image_128.to_base64())
        self.assertEqual(inline_data_part['metadata']['image_path'], f'/web/image/ai.agent/{self.rendering_record.id}/image_128')
