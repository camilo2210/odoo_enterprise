from odoo import Command
from odoo.addons.ai.tests.common import mock_iap_results, TestAICommon
from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestAIDraftUI(HttpCase, TestAICommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        project = cls.env['project.project'].create({
            'name': 'Test Project',
        })
        stage = cls.env['project.task.type'].create([{
            'name': 'Test Stage',
            'project_ids': project.ids,
        }])
        cls.env['project.task'].create({
            'name': 'Test task',
            'project_id': project.id,
            'stage_id': stage.id,
            'partner_id': cls.env['res.partner'].create({
                'name': 'Freddy',
                'email': 'freddy@example.com',
            }).id,
        })
        cls.env.ref('base.user_admin').write({
            'email': 'mitchell.admin@example.com'
        })
        cls.env['ai.composer'].create({
            'name': 'agent composer',
            'interface_key': 'chatter_ai_button',
            'focused_model_id': cls.env['ir.model']._get_id('chatbot.script'),
            'available_prompt_ids': [Command.create({
                'name': 'chatbot prompt button',
            })],
        })

    def mock_api_responses(self):
        def response_generator():
            while True:
                yield self.mock_text_response("This is dummy ai response")
        return mock_iap_results(self.env, response_generator())

    def test_ai_draft_chatter_button(self):
        with self.mock_api_responses():
            self.start_tour("/odoo", 'test_ai_draft_chatter_button', login='admin')

    def test_ai_draft_html_field(self):
        with self.mock_api_responses():
            self.start_tour("/odoo", 'test_ai_draft_html_field', login='admin')

    def test_close_ai_chat_window(self):
        with self.mock_api_responses():
            self.start_tour("/odoo", 'test_close_ai_chat_window', login='admin')

    def test_ai_systray_button_fullscreen(self):
        with self.mock_api_responses():
            self.start_tour("/odoo/discuss", "test_ai_systray_discuss_fullscreen", login="admin")
