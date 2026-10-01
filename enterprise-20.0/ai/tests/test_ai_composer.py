# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError
from odoo.tests import tagged, mute_logger
from .common import TestAICommon


@tagged("post_install", "-at_install")
class TestAIComposer(TestAICommon):

    @mute_logger('odoo.sql_db')
    def test_unique_composer_constraint(self):
        """Creating two composers with the same interface_key and focused_model_id should raise,
        even for two different agents: the rule is unique system-wide, not per agent."""
        agent_a = self.env['ai.agent'].create({'name': 'Agent A'})
        agent_b = self.env['ai.agent'].create({'name': 'Agent B'})
        partner_model = self.env['ir.model']._get('res.partner')

        self.env['ai.composer'].create({
            'name': 'First',
            'interface_key': 'systray_ai_button',
            'ai_agent_id': agent_a.id,
            'focused_model_id': partner_model.id,
        })
        with self.assertRaises(IntegrityError):
            self.env['ai.composer'].create({
                'name': 'Second',
                'interface_key': 'systray_ai_button',
                'ai_agent_id': agent_b.id,
                'focused_model_id': partner_model.id,
            })

    @mute_logger('odoo.sql_db')
    def test_unique_composer_constraint_conflicts_with_system_default(self):
        """A new composer with no focused_model_id collides with the seeded system-default
        rule for that interface_key, since NULL models are not distinct from one another."""
        agent = self.env['ai.agent'].create({'name': 'Test Agent'})
        with self.assertRaises(IntegrityError):
            self.env['ai.composer'].create({
                'name': 'Custom Systray Default',
                'interface_key': 'systray_ai_button',
                'ai_agent_id': agent.id,
            })

    def test_unique_composer_constraint_different_models(self):
        """Creating composers with same agent and interface_key but different models should not raise."""
        agent = self.env['ai.agent'].create({'name': 'Test Agent'})
        partner_model = self.env['ir.model']._get('res.partner')
        mail_message_model = self.env['ir.model']._get('mail.message')

        self.env['ai.composer'].create({
            'name': 'Partner Composer',
            'interface_key': 'systray_ai_button',
            'ai_agent_id': agent.id,
            'focused_model_id': partner_model.id,
        })
        self.env['ai.composer'].create({
            'name': 'Mail Message Composer',
            'interface_key': 'systray_ai_button',
            'ai_agent_id': agent.id,
            'focused_model_id': mail_message_model.id,
        })

    def test_retrieve_transcription_composer(self):
        agent = self.env['ai.agent'].create({
            'name': 'Test AI Agent',
        })
        ai_agent_model = self.env['ir.model']._get('ai.agent')

        default_transcription_composer = self.env['ai.composer'].search([
            ('interface_key', '=', 'voice_transcription_component'),
            ('focused_model_id', '=', False),
        ], limit=1)

        ai_agent_transcription_composer = self.env['ai.composer'].create({
            'name': 'AI Agent Composer',
            'interface_key': 'voice_transcription_component',
            'ai_agent_id': agent.id,
            'focused_model_id': ai_agent_model.id,
        })

        res = self.env['ai.composer'].retrieve_transcription_composer('ai.agent')
        self.assertEqual(res['id'], ai_agent_transcription_composer.id, "Should retrieve the composer specific to ai.agent")
        res = self.env['ai.composer'].retrieve_transcription_composer(False)
        self.assertEqual(res['id'], default_transcription_composer.id, "Should retrieve the default composer when no model is provided")

    def test_file_viewer_ai_button_composer_context(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'test attachment',
            'raw': b'test',
        })
        composer = self.env['ai.composer'].create({
            'name': 'File Viewer Composer',
            'interface_key': 'file_viewer_ai_button',
            'focused_model_id': self.env['ir.model']._get_id('ir.attachment'),
        })
        context = composer._get_initial_context(res_model='ir.attachment', res_id=attachment.id)
        self.assertTrue(
            any("test attachment" in part['text'] for part in context),
            "The attachment name should be present in the context parts"
        )
