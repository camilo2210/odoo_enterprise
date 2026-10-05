import json
import io
from http import HTTPStatus
from unittest.mock import patch

from odoo.addons.base.tests.common import HttpCaseWithUserDemo
from odoo.addons.cloud_storage_google.tests.test_cloud_storage_google import TestCloudStorageGoogleCommon


class TestVoipCloudStorageGoogle(HttpCaseWithUserDemo, TestCloudStorageGoogleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prod_call = cls.env["voip.call"].create({
            "phone_number": "123",
            "user_id": cls.user_demo.id,
            "is_production": True,
        })
        cls.demo_call = cls.env["voip.call"].create({
            "phone_number": "456",
            "user_id": cls.user_demo.id,
            "is_production": False,
        })

    def test_voip_google_cloud_upload_success(self):
        """Test uploading a VoIP recording with Google Cloud Storage configured."""
        self.env["ir.config_parameter"].set_str("cloud_storage_provider", "google")
        self.authenticate(self.user_demo.login, self.user_demo.login)

        recording_data = b"fake audio data"
        response = self.url_open(
            f"/voip/upload_recording/{self.prod_call.id}",
            data={
                "csrf_token": self.csrf_token(),
                "cloud_storage": "true",
                "start_ms": 0,
                "end_ms": 1000,
            },
            files={"ufile": ("recording.wav", io.BytesIO(recording_data), "audio/wav")},
            method="POST",
        )
        response.raise_for_status()

        # Response contains Google Cloud upload information & cloud attachment created
        content = json.loads(response.content.decode("utf-8"))
        self.assertIn("upload_info", content)
        self.assertEqual(content["upload_info"]["method"], "PUT")
        self.assertIn("https://storage.googleapis.com/", content["upload_info"]["url"])
        artifact = self.env["mail.call.artifact"].search([("voip_call_id", "=", self.prod_call.id)], limit=1)
        self.assertTrue(artifact, "A call artifact should have been created")
        attachment = artifact.media_id
        self.assertEqual(attachment.type, "cloud_storage")
        # The attachment stores the base URL, while upload_info contains the signed URL with query params
        self.assertEqual(attachment.url, content["upload_info"]["url"].split("?")[0])

    def test_voip_google_cloud_enforcement_fail(self):
        """Test that production recordings fail if cloud storage is not configured."""
        self.authenticate(self.user_demo.login, self.user_demo.login)

        with patch("odoo.addons.voip.controllers.voip_controller.VoipController._is_cloud_storage_configured", return_value=False):
            response = self.url_open(
                f"/voip/upload_recording/{self.prod_call.id}",
                data={
                    "csrf_token": self.csrf_token(),
                    "cloud_storage": "true",
                    "start_ms": 0,
                    "end_ms": 1000,
                },
                files={"ufile": ("recording.wav", io.BytesIO(b"fake data"), "audio/wav")},
                method="POST",
            )
            self.assertEqual(
                response.status_code,
                HTTPStatus.BAD_REQUEST,
                "Should fail upload when cloud storage is mandatory but not configured."
            )

    def test_voip_google_cloud_demo_restriction(self):
        """Test that demo recordings are prohibited from cloud storage."""
        self.env["ir.config_parameter"].set_str("cloud_storage_provider", "google")
        self.authenticate(self.user_demo.login, self.user_demo.login)

        response = self.url_open(
            f"/voip/upload_recording/{self.demo_call.id}",
            data={
                "csrf_token": self.csrf_token(),
                "cloud_storage": "true",
                "start_ms": 0,
                "end_ms": 1000,
            },
            files={"ufile": ("demo.wav", io.BytesIO(b"demo data"), "audio/wav")},
            method="POST",
        )
        self.assertEqual(
            response.status_code,
            HTTPStatus.FORBIDDEN,
            "Should prohibit demo recordings from using cloud storage."
        )
        self.assertIn("Demo recordings cannot be stored in cloud storage", response.text)
