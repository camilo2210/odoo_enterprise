import io
from http import HTTPStatus
from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.ai.models.mail_call_artifact import TRANSCRIPTION_MAX_FILE_SIZE


@tagged('call_artifacts')
class TestVoipAiController(HttpCase):

    def test_upload_recording_stt_file_too_large(self):
        """Forbid uploading an STT file that is too large"""
        user_phone_operator = new_test_user(self.env, login='user_phone_operator')
        voip_call = self.env['voip.call'].create({
            'phone_number': '+1-202-555-0104',
            'user_id': user_phone_operator.id,
        })
        self.authenticate(user_phone_operator.login, user_phone_operator.login)
        csrf_token = self.csrf_token()
        stt_file = ('test.wav', io.BytesIO(b'a' * (TRANSCRIPTION_MAX_FILE_SIZE + 1)), 'audio/wav')
        with patch('odoo.addons.mail.models.mail_call_artifact.MailCallArtifact.create') as mock_create_artifact:
            # Create a dummy call.artifact record to be returned by the mock
            dummy_artifact = self.env['mail.call.artifact'].create({
                'voip_call_id': voip_call.id,
                'start_ms': 0,
                'end_ms': 1000,
            })
            mock_create_artifact.return_value = dummy_artifact

            response = self.url_open(
                f'/voip/upload_recording/{voip_call.id}?is_stt=true',
                files={'ufile': stt_file},
                data={'csrf_token': csrf_token, 'start_ms': 0, 'end_ms': 1000},
            )
            self.assertEqual(response.status_code, 403,
                "Response should be 403 Forbidden for a file that is too large")

    def test_upload_recording_stt_file_ok_size(self):
        """Verify that uploading an STT file with an acceptable size is successful"""
        user_phone_operator = new_test_user(self.env, login='user_phone_operator_2')
        voip_call = self.env['voip.call'].create({
            'phone_number': '+1-202-555-0105',
            'user_id': user_phone_operator.id,
        })
        self.authenticate(user_phone_operator.login, user_phone_operator.login)
        csrf_token = self.csrf_token()
        stt_file = ('test.wav', io.BytesIO(b'a' * (TRANSCRIPTION_MAX_FILE_SIZE - 1)), 'audio/wav')
        # We patch to avoid creating artifacts and attachments
        with patch('odoo.addons.mail.models.mail_call_artifact.MailCallArtifact.create') as mock_create_artifact:
            # Create a dummy call.artifact record to be returned by the mock
            dummy_artifact = self.env['mail.call.artifact'].create({
                'voip_call_id': voip_call.id,
                'start_ms': 0,
                'end_ms': 1000,
            })
            mock_create_artifact.return_value = dummy_artifact

            response = self.url_open(
                f'/voip/upload_recording/{voip_call.id}?is_stt=true',
                files={'ufile': stt_file},
                data={'csrf_token': csrf_token, 'start_ms': 0, 'end_ms': 1000},
            )
            self.assertEqual(response.status_code, 200, "Response should be 200 OK for a file with a valid size")
            # Check that the ORM create was reached with correct values
            self.assertTrue(mock_create_artifact.called, "MailCallArtifact.create should have been called")
            args, _kwargs = mock_create_artifact.call_args
            self.assertTrue(args[0].get('is_stt'), "The artifact should be marked as STT")

    def test_upload_stt_recording_bypass_cloud_storage_requirement(self):
        user = new_test_user(self.env, login="stt_user")
        voip_call = self.env["voip.call"].create({
            "phone_number": "789",
            "user_id": user.id,
            "is_production": True,
        })
        self.authenticate(user.login, user.login)

        # Enable cloud storage in config
        self.env["ir.config_parameter"].sudo().set_str("cloud_storage_provider", "google")

        # SUCCESS: STT chunks should be allowed to upload to Odoo even without cloud flag
        stt_file = ('test.wav', io.BytesIO(b'audio data'), 'audio/wav')
        response = self.url_open(
            f"/voip/upload_recording/{voip_call.id}?is_stt=true",
            data={
                "csrf_token": self.csrf_token(),
                "cloud_storage": "false",
                "start_ms": 0,
                "end_ms": 1000,
            },
            files={"ufile": stt_file},
            method="POST",
        )
        self.assertEqual(
            response.status_code,
            HTTPStatus.OK,
            "STT chunks must be allowed to bypass cloud storage requirement"
        )
