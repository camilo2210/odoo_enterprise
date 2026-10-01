from unittest.mock import patch

from odoo.addons.mail.tests.common import MailCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged
from odoo.tools import mute_logger


@tagged("call_artifacts")
class TestVoipAiFlow(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.user_employee
        cls.audio_data = b"RIFF\x00\x00\x00\x00WAVEfmt\x00data\x00\x00\x00\x00"

    def setUp(self):
        """Simulate situation where we are after call with policy forcing transcription."""
        super().setUp()
        self.call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "user_id": self.user.id,
        })

        # Create artifact
        self.artifact = self.env['mail.call.artifact'].create({
            'voip_call_id': self.call.id,
            'start_ms': 0,
            'end_ms': 1000,
            'is_stt': True,
            'transcription_state': 'pending',
        })

        # Create attachment for artifact
        self.attachment = self.env['ir.attachment'].create({
            'name': 'audio.webm',
            'type': 'binary',
            'mimetype': 'audio/webm; codecs=opus',
            'raw': self.audio_data,
            'res_model': 'mail.call.artifact',
            'res_id': self.artifact.id,
        })

    def test_transcription_success_cleanup_and_summary(self):
        """
        Scenario: Transcription requested sucessfully.
        -> Artifact state 'done'
        -> Media attachment is DELETED (cleanup)
        -> Call summary is GENERATED
        """
        # Mock LLM service and prevent commit from breaking the test
        with patch('odoo.addons.ai.models.mail_call_artifact.call_odoo_ai') as mock_transcribe, \
             patch('odoo.addons.ai.models.ai_agent.AIAgent._generate_single_response') as mock_llm, \
             patch.object(self.env.cr, 'commit'):

            mock_transcribe.return_value = {'status': 'success', 'text': "This is a transcribed text."}
            mock_llm.return_value = [{'type': 'text', 'text': "Summary of the call."}]

            self.artifact.action_transcribe_gevent()

            self.artifact.invalidate_recordset()
            self.call.invalidate_recordset()

            self.assertEqual(self.artifact.transcription_state, 'done')
            self.assertEqual(self.artifact.transcript, "This is a transcribed text.")
            self.assertFalse(self.attachment.exists(), "Media attachment should be deleted after successful transcription.")
            self.assertEqual(self.call.summary, "Summary of the call.")

    @mute_logger('odoo.addons.ai.models.mail_call_artifact')
    def test_transcription_terminal_error_cleanup(self):
        """
        Scenario: Transcription fails terminally (max retries reached).
        Checks:
        - Artifact state becomes 'error'
        - Media attachment is DELETED (cleanup)
        """
        # Set max retries to 1 for easier testing
        self.env['ir.config_parameter'].sudo().set_int('ai.max_transcription_retries', 1)

        # Mock LLM service to raise exception and prevent commit from breaking the test
        with (
            patch(
                'odoo.addons.ai.utils.ai_utils.call_odoo_ai',
                side_effect=UserError("Mocked API Error")
            ),
            patch.object(self.env.cr, 'commit')
        ):

            self.artifact.action_transcribe_gevent()
            self.artifact.invalidate_recordset()

            self.assertEqual(self.artifact.transcription_state, 'error')
            self.assertEqual(self.artifact.transcription_error_count, 1)
            self.assertFalse(self.attachment.exists(), "Media attachment should be deleted after terminal transcription error.")
            self.assertFalse(self.artifact.media_id, "Artifact media_id field should be empty.")
