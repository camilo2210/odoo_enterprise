import struct
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.tools import BinaryBytes

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.tests.common_voip import VoipPhoneServiceCase, pbx_router

UPLOAD_SOUND_ROUTE = "/api/phone_service/1/pbx/upload_sound"


def _wav_data():
    frames = b"\0\0" * 8
    return BinaryBytes(b"".join((
        b"RIFF",
        struct.pack("<I", 36 + len(frames)),
        b"WAVEfmt ",
        struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16),
        b"data",
        struct.pack("<I", len(frames)),
        frames,
    )))


@tagged("post_install", "-at_install")
class TestVoipSound(VoipPhoneServiceCase):
    def _capture_upload_sound(self):
        calls = []

        def side_effect(route, params, **kw):
            calls.append((route, params))
            return pbx_router(route, params)

        return calls, side_effect

    def test_upload_sound_requires_file(self):
        with self.assertRaises(ValidationError):
            self.env["voip.sound"].create({
                "name": "Greeting",
                "source_type": "upload",
            })

    def test_tts_sound_requires_text_and_voice(self):
        test_cases = [
            {"tts_text": "Welcome", "tts_voice": False},
            {"tts_voice": "Telnyx.NaturalHD.astra"},
        ]
        for vals in test_cases:
            with self.subTest(vals=vals), self.assertRaises(ValidationError):
                self.env["voip.sound"].create({
                    "name": "Greeting",
                    "source_type": "tts",
                    **vals,
                })

    def test_entering_tts_text_selects_the_tts_source(self):
        form = Form(self.env["voip.sound"], view="voip.voip_sound_view_form")

        form.tts_text = "Welcome"

        self.assertEqual(form.source_type, "tts")

    def test_clearing_tts_text_restores_the_uploaded_source(self):
        message = self.env["voip.sound"].create({
            "name": "Greeting",
            "source_type": "upload",
            "data": _wav_data(),
            "data_filename": "greeting.wav",
        })
        form = Form(message, view="voip.voip_sound_view_form")

        form.tts_text = "Welcome"
        self.assertEqual(form.source_type, "tts")

        form.tts_text = ""
        self.assertEqual(form.source_type, "upload")
        form.save()

    def test_create_upload_sound_syncs_pbx(self):
        calls, side_effect = self._capture_upload_sound()

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=side_effect):
            message = self.env["voip.sound"].create({
                "name": "Greeting",
                "source_type": "upload",
                "data": _wav_data(),
                "data_filename": "greeting.wav",
            })

        upload_calls = [params for route, params in calls if route == UPLOAD_SOUND_ROUTE]
        self.assertEqual(len(upload_calls), 1)
        self.assertEqual(upload_calls[0]["filename"], f"odoo_audio_message_{message.id}")
        self.assertEqual(upload_calls[0]["sound_format"], "wav")

    def test_create_tts_sound_requires_generated_audio(self):
        calls, side_effect = self._capture_upload_sound()

        with (
            patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=side_effect),
            self.assertRaisesRegex(ValidationError, "Generate the audio"),
        ):
            self.env["voip.sound"].create({
                "name": "Greeting",
                "source_type": "tts",
                "tts_text": "Welcome",
                "tts_voice": "Telnyx.NaturalHD.astra",
            })

        self.assertFalse([c for c in calls if c[0] == UPLOAD_SOUND_ROUTE])

    def test_write_sound_data_increments_version_and_syncs_pbx(self):
        message = self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Greeting",
            "source_type": "upload",
            "data": _wav_data(),
            "data_filename": "greeting.wav",
        })
        calls, side_effect = self._capture_upload_sound()

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=side_effect):
            message.with_context(voip_skip_pbx_sync=False).write({
                "data": _wav_data(),
            })

        self.assertEqual(message.data_version, 1)
        upload_calls = [params for route, params in calls if route == UPLOAD_SOUND_ROUTE]
        self.assertEqual(len(upload_calls), 1)
        self.assertEqual(upload_calls[0]["filename"], f"odoo_audio_message_{message.id}")
        self.assertEqual(upload_calls[0]["sound_format"], "wav")

    def test_uploaded_sound_rejects_non_wav_filename(self):
        message = self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Greeting",
            "source_type": "upload",
            "data": _wav_data(),
            "data_filename": "greeting.wav",
        })
        calls, side_effect = self._capture_upload_sound()

        with (
            patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=side_effect),
            self.assertRaises(ValidationError),
        ):
            message.with_context(voip_skip_pbx_sync=False).data_filename = "greeting.mp3"

        self.assertEqual(message.data_version, 0)
        self.assertFalse([params for route, params in calls if route == UPLOAD_SOUND_ROUTE])

    def test_uploaded_sound_rejects_invalid_wav(self):
        with self.assertRaisesRegex(ValidationError, "valid WAV"):
            self.env["voip.sound"].create({
                "name": "Greeting",
                "source_type": "upload",
                "data": BinaryBytes(b"not-a-wav"),
                "data_filename": "greeting.wav",
            })

    def test_sound_skip_context_does_not_sync_pbx(self):
        calls, side_effect = self._capture_upload_sound()

        with patch.object(PhoneServiceAPI, "_call_phone_service", side_effect=side_effect):
            self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
                "name": "Greeting",
                "source_type": "upload",
                "data": _wav_data(),
                "data_filename": "greeting.wav",
            })

        self.assertFalse([c for c in calls if c[0] == UPLOAD_SOUND_ROUTE])
