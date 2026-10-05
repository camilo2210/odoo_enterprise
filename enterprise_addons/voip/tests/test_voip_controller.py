from http import HTTPStatus
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase, JsonRpcException, new_test_user
from odoo.tools import BinaryBytes, mute_logger

from odoo.addons.voip.tools.wav import encode_wav, pack_int16_samples

HANGUP_CALL = "odoo.addons.voip.models.phone_service_api.PhoneServiceAPI.hangup_call"
DECLINE_CALL = "odoo.addons.voip.models.phone_service_api.PhoneServiceAPI.decline_call"


@tagged("-at_install", "post_install")
class TestVoipController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="voip_user")

    def _make_incoming_call(self, user, conversation, pbx_call_id=None, wakeup_pbx_call_id=None):
        call = self.env["voip.call"].create({
            "phone_number": "+15550001111",
            "direction": "incoming",
            "user_id": user.id,
            "conversation_id": conversation.id,
            "wakeup_pbx_call_id": wakeup_pbx_call_id,
        })
        if pbx_call_id:
            self.env["voip.call.leg"].create({
                "conversation_id": conversation.id,
                "voip_call_id": call.id,
                "role": "participant",
                "pbx_call_id": pbx_call_id,
            })
        return call

    def _make_conversation(self, identifier):
        return self.env["voip.conversation"].create({
            "conversation_identifier": identifier,
        })

    def test_decline_incoming_call_hangs_up_own_leg_via_pbx(self):
        owner = new_test_user(self.env, login="voip_decline_owner")
        conversation = self._make_conversation("conv-decline")
        call = self._make_incoming_call(
            owner, conversation, pbx_call_id="wazo-leg-owner",
            wakeup_pbx_call_id="wazo-wakeup-ignored-when-leg-exists")

        self.authenticate(owner.login, owner.password)
        with patch(HANGUP_CALL) as hangup_call:
            result = self.make_jsonrpc_request(
                "/voip/decline_incoming_call", {"call_id": call.id})

        self.assertTrue(result["success"])
        hangup_call.assert_called_once_with("wazo-leg-owner")
        call.invalidate_recordset()
        self.assertEqual(call.state, "rejected")

    def test_decline_group_call_hangs_up_only_declining_members_leg(self):
        conversation = self._make_conversation("conv-group-decline")
        decliner = new_test_user(self.env, login="voip_group_decliner")
        colleague = new_test_user(self.env, login="voip_group_colleague")
        decliner_call = self._make_incoming_call(decliner, conversation, pbx_call_id="wazo-leg-decliner")
        colleague_call = self._make_incoming_call(colleague, conversation, pbx_call_id="wazo-leg-colleague")

        self.authenticate(decliner.login, decliner.password)
        with patch(HANGUP_CALL) as hangup_call:
            self.make_jsonrpc_request(
                "/voip/decline_incoming_call", {"call_id": decliner_call.id})

        hangup_call.assert_called_once_with("wazo-leg-decliner")
        decliner_call.invalidate_recordset()
        colleague_call.invalidate_recordset()
        self.assertEqual(decliner_call.state, "rejected")
        self.assertEqual(colleague_call.state, "calling")

    def test_decline_push_only_call_asks_the_pbx_to_resolve_the_ring_leg(self):
        # A member reached by push alone owns no channel the client can name:
        # the push names the caller's own on a direct call. The PBX is asked to
        # stop ringing this member of this conversation, and works out which
        # channel that is.
        owner = new_test_user(self.env, login="voip_decline_pushonly")
        owner.voip_pbx_user_uuid = "pbx-uuid-pushonly"
        conversation = self._make_conversation("conv-pushonly")
        call = self._make_incoming_call(owner, conversation, wakeup_pbx_call_id="wazo-wakeup-owner")

        self.authenticate(owner.login, owner.password)
        with patch(HANGUP_CALL) as hangup_call, patch(DECLINE_CALL) as decline_call:
            result = self.make_jsonrpc_request(
                "/voip/decline_incoming_call", {"call_id": call.id})

        self.assertTrue(result["success"])
        decline_call.assert_called_once_with("conv-pushonly", "pbx-uuid-pushonly")
        hangup_call.assert_not_called()
        call.invalidate_recordset()
        self.assertEqual(call.state, "rejected")

    def test_decline_call_of_a_user_without_pbx_identity_is_noop(self):
        # Nothing identifies this member to the PBX, so the call is settled in
        # Odoo alone and the ring times out by itself.
        owner = new_test_user(self.env, login="voip_decline_nohandle")
        conversation = self._make_conversation("conv-nohandle")
        call = self._make_incoming_call(owner, conversation)

        self.authenticate(owner.login, owner.password)
        with patch(HANGUP_CALL) as hangup_call, patch(DECLINE_CALL) as decline_call:
            result = self.make_jsonrpc_request(
                "/voip/decline_incoming_call", {"call_id": call.id})

        self.assertTrue(result["success"])
        hangup_call.assert_not_called()
        decline_call.assert_not_called()
        call.invalidate_recordset()
        self.assertEqual(call.state, "rejected")

    @mute_logger("odoo.addons.base.models.ir_access", "odoo.http")
    def test_decline_incoming_call_forbidden_for_non_owner(self):
        owner = new_test_user(self.env, login="voip_decline_owner2")
        conversation = self._make_conversation("conv-decline-2")
        call = self._make_incoming_call(owner, conversation, pbx_call_id="wazo-leg-owner2")
        intruder = new_test_user(self.env, login="voip_decline_intruder")

        self.authenticate(intruder.login, intruder.password)
        with patch(HANGUP_CALL) as hangup_call, self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request(
                "/voip/decline_incoming_call", {"call_id": call.id})

        hangup_call.assert_not_called()

    def test_parse_phone_number_uses_formatted_country(self):
        user = new_test_user(self.env, login="voip_parse_user")
        us_country = self.env["res.country"].search([("code", "=ilike", "US")], limit=1)

        self.authenticate(user.login, user.password)
        with (
            patch("odoo.addons.voip.controllers.voip_controller.extract_country_code") as extract_country_code,
            patch("odoo.addons.voip.controllers.voip_controller.phone_format") as phone_format,
        ):
            extract_country_code.side_effect = [
                {"iso": "", "itu": ""},
                {"iso": "us", "itu": "1"},
            ]
            phone_format.return_value = "+1 650-419-3846"
            result = self.make_jsonrpc_request(
                "/voip/parse_phone_number",
                {
                    "data": {
                        "phone_number": "1(650) 419-3846",
                        "iso": "be",
                        "itu": "32",
                    },
                },
            )

        self.assertEqual(result["countryId"], us_country.id)
        self.assertEqual(result["phone_number"], "+1 650-419-3846")
        self.assertTrue(result["isValid"])

    def test_recording_can_only_be_uploaded_by_owner_of_the_call(self):
        rightful_record_owner = new_test_user(self.env, login="based VoIP user 😤")
        # Use Demo mode to verify generic ownership without being blocked by cloud enforcement
        call = self.env["voip.call"].create({
            "phone_number": "0491 577 644",
            "user_id": rightful_record_owner.id,
            "is_production": False,
        })
        evil_uploader = new_test_user(self.env, login="evil uploader 👺")

        self.authenticate(evil_uploader.login, evil_uploader.password)
        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token()},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        self.authenticate(rightful_record_owner.login, rightful_record_owner.password)
        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token(), "start_ms": 100, "end_ms": 5000},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        call.invalidate_recordset()
        # The controller creates a call.artifact, NOT a direct attachment on the call
        artifact = self.env["mail.call.artifact"].search([("voip_call_id", "=", call.id)], limit=1)
        self.assertTrue(artifact, "A call artifact should have been created")
        self.assertEqual(artifact.start_ms, 100)
        self.assertEqual(artifact.end_ms, 5000)

        attachment = artifact.media_id
        self.assertTrue(attachment, "Attachment should be linked to the artifact")
        self.assertTrue(attachment.name.endswith(".ogg"))
        self.assertEqual(attachment.res_model, "mail.call.artifact")
        self.assertEqual(attachment.res_id, artifact.id)

        # Check read access for the user (via the artifact/call access rules)
        self.env.invalidate_all()
        try:
            attachment.with_user(rightful_record_owner).read(["raw"])
        except Exception as e:  # noqa: BLE001
            self.fail(f"User should be able to read the call recording attachment: {e}")

    def test_voip_call_spawns_artifacts_happy_path(self):
        # Use Demo mode to verify artifact spawning logic
        call = self.env["voip.call"].create({
            "phone_number": "0491 577 644",
            "user_id": self.user.id,
            "is_production": False,
        })
        self.authenticate(self.user.login, self.user.password)

        # First upload
        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={
                "csrf_token": self.csrf_token(),
                "start_ms": 0,
                "end_ms": 1000,
            },
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        call.invalidate_recordset()
        # Verify artifact creation instead of direct media_id on call
        self.assertTrue(call.artifact_ids, "First upload should succeed")
        self.assertEqual(len(call.artifact_ids), 1)

        # Second upload attempt - Should be allowed with Artifacts
        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={
                "csrf_token": self.csrf_token(),
                "start_ms": 1000,
                "end_ms": 2000,
            },
            files={"ufile": ("second_recording.m4a", b"mp4", "audio/mp4")},
            method="POST",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        call.invalidate_recordset()
        self.assertEqual(len(call.artifact_ids), 2, "Second upload should create a second artifact")
        self.assertTrue(call.artifact_ids.sorted("start_ms")[1].media_id.name.endswith(".m4a"))

    def test_upload_recording_requires_a_file(self):
        call = self.env["voip.call"].create({
            "phone_number": "0491577644", "user_id": self.user.id, "is_production": False,
        })
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token()},
            files={"ufile": ("", b"", "application/octet-stream")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_upload_recording_rejects_non_audio_content_type(self):
        call = self.env["voip.call"].create({
            "phone_number": "0491577644", "user_id": self.user.id, "is_production": False,
        })
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token()},
            files={"ufile": ("notes.txt", b"hello", "text/plain")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    def test_upload_recording_rejects_a_nonexistent_call(self):
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            "/voip/upload_recording/999999999",
            data={"csrf_token": self.csrf_token()},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_upload_recording_demo_mode_enforces_a_3_minute_limit(self):
        call = self.env["voip.call"].create({
            "phone_number": "0491577644", "user_id": self.user.id, "is_production": False,
        })
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token(), "start_ms": 0, "end_ms": 4 * 60 * 1000},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_upload_recording_demo_mode_forbids_cloud_storage(self):
        call = self.env["voip.call"].create({
            "phone_number": "0491577644", "user_id": self.user.id, "is_production": False,
        })
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token(), "cloud_storage": "true"},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_upload_recording_production_requires_cloud_storage_to_be_configured(self):
        call = self.env["voip.call"].create({
            "phone_number": "0491577644", "user_id": self.user.id, "is_production": True,
        })
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token(), "cloud_storage": "true"},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_upload_recording_production_requires_the_client_to_request_cloud_storage(self):
        self.env["ir.config_parameter"].sudo().set_str("cloud_storage_provider", "test_provider")
        call = self.env["voip.call"].create({
            "phone_number": "0491577644", "user_id": self.user.id, "is_production": True,
        })
        self.authenticate(self.user.login, self.user.password)

        response = self.url_open(
            f"/voip/upload_recording/{call.id}",
            data={"csrf_token": self.csrf_token()},
            files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
            method="POST",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

    def test_audio_message_route_streams_the_file(self):
        admin = new_test_user(self.env, login="voip_audio_admin", groups="voip.group_voip_admin")
        wav_bytes = encode_wav(
            pack_int16_samples([0] * 8), channels=1, sample_width=2, frame_rate=8000,
        )
        message = self.env["voip.sound"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Greeting",
            "source_type": "upload",
            "data": BinaryBytes(wav_bytes),
            "data_filename": "greeting.wav",
        })

        self.authenticate(admin.login, admin.password)
        response = self.url_open(f"/voip/audio/message/{message.id}")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, wav_bytes)

    def test_audio_message_route_404_for_unknown_id(self):
        admin = new_test_user(self.env, login="voip_audio_admin_404", groups="voip.group_voip_admin")
        self.authenticate(admin.login, admin.password)

        response = self.url_open("/voip/audio/message/999999999")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_voicemail_message_route_streams_the_recording(self):
        admin = new_test_user(self.env, login="voip_vm_admin", groups="voip.group_voip_admin")
        mailbox = self.env["voip.voicemail"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support", "email": "support@example.com", "pbx_voicemail_id": 555,
        })
        message = self.env["voip.voicemail.message"].sudo().create({
            "event_id": "evt-controller-1",
            "pbx_message_id": "msg-controller-1",
            "voicemail_id": mailbox.id,
            "occurred_at": "2026-01-01 10:00:00",
            "recording": BinaryBytes(b"fake-recording-bytes"),
            "recording_filename": "voicemail_555_msg-controller-1.wav",
        })

        self.authenticate(admin.login, admin.password)
        response = self.url_open(f"/voip/voicemail/message/{message.id}")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.content, b"fake-recording-bytes")

    def test_voicemail_message_route_404_without_recording_or_unknown_id(self):
        admin = new_test_user(self.env, login="voip_vm_admin_404", groups="voip.group_voip_admin")
        mailbox = self.env["voip.voicemail"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support", "email": "support@example.com", "pbx_voicemail_id": 556,
        })
        message_without_recording = self.env["voip.voicemail.message"].sudo().create({
            "event_id": "evt-controller-2",
            "pbx_message_id": "msg-controller-2",
            "voicemail_id": mailbox.id,
            "occurred_at": "2026-01-01 10:00:00",
        })

        self.authenticate(admin.login, admin.password)

        response = self.url_open(f"/voip/voicemail/message/{message_without_recording.id}")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

        response = self.url_open("/voip/voicemail/message/999999999")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
