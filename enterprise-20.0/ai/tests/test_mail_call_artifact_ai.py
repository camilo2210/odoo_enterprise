import logging
from datetime import UTC, datetime
from unittest.mock import patch

from odoo import fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import (
    HttpCase,
    JsonRpcException,
    TransactionCase,
    new_test_user,
)
from odoo.tools import mute_logger

from odoo.addons.mail.tools import discuss, jwt

_logger = logging.getLogger(__name__)


@tagged("call_artifacts")
class TestMailCallArtifactAI(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        channel = cls.env['discuss.channel'].create({'name': 'Test Channel'})
        cls.call = cls.env['discuss.call.history'].create({
            'start_dt': '2023-01-01 10:00:00',
            'channel_id': channel.id,
        })

    def _create_stt_artifact(self, start_ms=0, end_ms=1000, **values):
        artifact_values = {
            "discuss_call_history_id": self.call.id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "is_stt": True,
            "transcription_state": "pending",
        }
        artifact_values.update(values)
        artifact = self.env["mail.call.artifact"].create(artifact_values)
        self.env["ir.attachment"].create({
            "name": "transcription.webm",
            "raw": b"transcription",
            "res_model": artifact._name,
            "res_id": artifact.id,
            "mimetype": "audio/webm",
        })
        artifact.invalidate_recordset(["media_id"])
        return artifact

    def _create_media_artifact(self, start_ms=0, end_ms=1000):
        artifact = self.env["mail.call.artifact"].create({
            "discuss_call_history_id": self.call.id,
            "start_ms": start_ms,
            "end_ms": end_ms,
        })
        self.env["ir.attachment"].create({
            "name": "recording.ogg",
            "raw": b"recording",
            "res_model": artifact._name,
            "res_id": artifact.id,
            "mimetype": "audio/ogg",
        })
        artifact.invalidate_recordset(["media_id"])
        return artifact

    def _assert_transcription_email_target(self, artifact, expected_target):
        with patch.object(
            self.env.registry["mail.call.artifact"],
            "_send_recording_available_email",
            autospec=True,
        ) as send_email:
            artifact._after_transcription_done()
        self.assertFalse(artifact.media_id)
        if expected_target:
            send_email.assert_called_once_with(expected_target)
        else:
            send_email.assert_not_called()

    def test_has_transcript(self):
        artifact = self._create_stt_artifact()
        other_call = self.env["discuss.call.history"].create({
            "channel_id": self.call.channel_id.id,
            "start_dt": "2023-01-01 11:00:00",
        })
        transcript_domain = [
            ("id", "in", (self.call | other_call).ids),
            ("has_transcript", "=", True),
        ]
        self.assertFalse(self.call.has_transcript)
        self.assertFalse(self.call.has_recording)
        self.assertFalse(self.call.search(transcript_domain))

        artifact.write({
            "transcript": "WEBVTT\n\n00:00.000 --> 00:01.000\nHello",
            "transcription_state": "done",
        })

        self.assertTrue(self.call.has_transcript)
        self.assertFalse(self.call.has_recording)
        self.assertEqual(self.call.search(transcript_domain), self.call)

    def test_recording_flags_exclude_transcription_audio(self):
        artifact = self._create_stt_artifact()
        for is_stt in (True, False, True):
            artifact.is_stt = is_stt
            self.assertEqual(self.call.has_recording, not is_stt)
            self.assertEqual(self.call.has_audio, not is_stt)
            self.assertFalse(self.call.has_video)

    def test_recording_waits_for_matching_transcription(self):
        media_artifact = self._create_media_artifact()
        self.assertTrue(media_artifact._is_recording_available())

        stt_artifact = self._create_stt_artifact()
        self.assertFalse(stt_artifact._is_recording_media())
        self.assertFalse(media_artifact._is_recording_available())

        stt_artifact.transcription_state = "error"
        self.assertFalse(media_artifact._is_recording_available())

        stt_artifact.transcription_state = "done"
        self.assertTrue(media_artifact._is_recording_available())

        matching_stt_artifact = self._create_stt_artifact()
        self.assertFalse(media_artifact._is_recording_available())
        matching_stt_artifact.transcription_state = "done"
        self.assertTrue(media_artifact._is_recording_available())

        other_stt_artifact = self.env["mail.call.artifact"].create({
            "discuss_call_history_id": self.call.id,
            "start_ms": 1000,
            "end_ms": 2000,
            "is_stt": True,
            "transcription_state": "pending",
        })
        self.assertTrue(media_artifact._is_recording_available())
        self.assertFalse(other_stt_artifact._is_recording_available())

    def test_transcription_targets_recording_email_artifact(self):
        stt_only_artifact = self._create_stt_artifact(
            has_media_output=False,
            transcription_state="done",
        )
        self._assert_transcription_email_target(stt_only_artifact, stt_only_artifact)
        self.assertTrue(stt_only_artifact._is_recording_available())

        media_artifact = self._create_media_artifact(2000, 3000)
        stt_artifact = self._create_stt_artifact(
            2000,
            3000,
            has_media_output=True,
            transcription_state="done",
        )
        self._assert_transcription_email_target(stt_artifact, media_artifact)

        waiting_stt_artifact = self._create_stt_artifact(
            4000,
            5000,
            has_media_output=True,
            transcription_state="done",
        )
        self._assert_transcription_email_target(waiting_stt_artifact, False)

    def test_allow_stt_artifact_overlapping_non_stt_artifact(self):
        """Allow STT artifacts to have overlapping media windows"""
        # Archival Artifact (non-stt)
        self.env['mail.call.artifact'].create({
            'discuss_call_history_id': self.call.id,
            'start_ms': 0,
            'end_ms': 5000,
        })

        # STT Artifact that overlaps
        self.env['mail.call.artifact'].create({
            'discuss_call_history_id': self.call.id,
            'start_ms': 4000,
            'end_ms': 9000,
            'is_stt': True,
        })

    def test_allow_overlap_of_two_stt_artifacts(self):
        """Bypass the standard overlap check for STT artifacts, as their internal VTT timestamps can naturally offset the chunk boundaries"""
        self.env['mail.call.artifact'].create({
            'discuss_call_history_id': self.call.id,
            'start_ms': 0,
            'end_ms': 5000,
            'is_stt': True,
            'transcript': '\n'.join(('WEBVTT',  # noqa: FLY002
                '',
                '00:00.000 --> 00:05.000',
                'Have you seen Mark'
            )),
        })

        self.env['mail.call.artifact'].create({
            'discuss_call_history_id': self.call.id,
            'start_ms': 3000,
            'end_ms': 8000,
            'is_stt': True,
            'transcript': '\n'.join(('WEBVTT',  # noqa: FLY002
                '',
                '00:06.000 --> 00:08.000',
                'Hello Rob! Yes, he sweeps the saloon'
            )),
        })

    @mute_logger('odoo.addons.ai.models.mail_call_artifact')
    def test_missing_transcription_retries(self):
        rec = self._create_stt_artifact()
        self.env["ir.config_parameter"].sudo().set_int("ai.max_transcription_retries", 2)

        with (
            self.enter_registry_test_mode(),
            patch(
                "odoo.addons.ai.models.mail_call_artifact.call_odoo_ai",
                side_effect=[{"text": None}, {"text": ""}],
            ),
            patch.object(self.env.cr, "commit"),
            patch.object(
                self.env.registry["mail.call.artifact"],
                "_send_recording_available_email",
                autospec=True,
            ) as send_email,
        ):
            rec.action_transcribe_gevent()
            rec.invalidate_recordset()
            self.assertEqual(rec.transcription_state, "pending")
            self.assertEqual(rec.transcription_error_count, 1)
            self.assertTrue(rec.media_id)
            send_email.assert_not_called()

            rec.action_transcribe_gevent()
            rec.invalidate_recordset()
            self.assertEqual(rec.transcription_state, "done")
            self.assertEqual(rec.transcription_error_count, 0)
            self.assertFalse(rec.media_id)
            send_email.assert_called_once_with(rec)

    @mute_logger('odoo.addons.ai.models.mail_call_artifact')
    def test_transcription_retry(self):
        """Verify that API errors trigger a retry (state remains pending) until max retries is reached"""
        rec = self._create_stt_artifact()
        self.env["ir.config_parameter"].sudo().set_int("ai.max_transcription_retries", 2)

        with (
            self.enter_registry_test_mode(),
            patch(
                'odoo.addons.ai.utils.ai_utils.call_odoo_ai',
                side_effect=UserError("Mocked API Error")
            ),
            patch.object(self.env.cr, 'commit')
        ):

            # 1st attempt
            rec.action_transcribe_gevent()
            rec.invalidate_recordset()
            self.assertEqual(rec.transcription_state, 'pending', "Should stay pending after 1st failure")
            self.assertEqual(rec.transcription_error_count, 1)

            # 2nd attempt
            rec.action_transcribe_gevent()
            rec.invalidate_recordset()
            self.assertEqual(rec.transcription_state, 'error', "Should be error after max retries")
            self.assertEqual(rec.transcription_error_count, 2)
            self.assertEqual(rec.transcription_error_msg, "Transcription request failed")


@tagged("call_artifacts")
class TestMailCallArtifactController(HttpCase):
    def test_recording_permissions_enable_transcription(self):
        permissions = self.env["discuss.channel.member"]._get_recording_permissions(
            self.env.user,
        )
        self.assertEqual(
            permissions,
            {
                "audioRecording": True,
                "transcription": True,
                "videoRecording": True,
            },
        )

    def test_transcribe_recording(self):
        recording_user = mail_new_test_user(self.env, login="recording_user")
        deleted_user = mail_new_test_user(self.env, login="deleted_recording_user")
        call_start = datetime(2023, 1, 1, 10)
        channel = self.env["discuss.channel"].create({"name": "Recorded Channel"})
        call = self.env["discuss.call.history"].create({
            "channel_id": channel.id,
            "start_dt": call_start,
        })
        call_start_ms = int(call_start.replace(tzinfo=UTC).timestamp() * 1000)
        issued_at = int(datetime.now(UTC).timestamp())
        sfu_key = discuss.get_derived_sfu_key(self.env, channel.id)
        token = jwt.sign(
            {"iat": issued_at, "user_id": recording_user.id},
            sfu_key,
            ttl=60,
            algorithm=jwt.Algorithm.HS256,
        )
        legacy_token = jwt.sign(
            {"iat": issued_at},
            sfu_key,
            ttl=60,
            algorithm=jwt.Algorithm.HS256,
        )
        deleted_user_token = jwt.sign(
            {"iat": issued_at, "user_id": deleted_user.id},
            sfu_key,
            ttl=60,
            algorithm=jwt.Algorithm.HS256,
        )
        deleted_user.unlink()
        with (
            patch.object(
                self.env.registry["mail.call.artifact"],
                "action_transcribe_gevent",
                autospec=True,
            ) as action_transcribe,
            patch.object(
                self.env.registry["discuss.call.history"],
                "_broadcast_recording_availability",
                autospec=True,
            ) as broadcast_recording,
        ):
            response = self.url_open(
                f"/mail/rtc/recording/{call.id}/transcribe",
                data=b"audio",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "audio/ogg",
                },
                params={
                    "start_ms": call_start_ms + 1_000,
                    "end_ms": call_start_ms + 3_000,
                    "has_media_output": "0",
                },
            )
            legacy_response = self.url_open(
                f"/mail/rtc/recording/{call.id}/transcribe",
                data=b"legacy audio",
                headers={
                    "Authorization": f"Bearer {legacy_token}",
                    "Content-Type": "audio/ogg",
                },
                params={
                    "start_ms": call_start_ms + 4_000,
                    "end_ms": call_start_ms + 6_000,
                },
            )
            deleted_user_response = self.url_open(
                f"/mail/rtc/recording/{call.id}/transcribe",
                data=b"deleted user audio",
                headers={
                    "Authorization": f"Bearer {deleted_user_token}",
                    "Content-Type": "audio/ogg",
                },
                params={
                    "start_ms": call_start_ms + 7_000,
                    "end_ms": call_start_ms + 9_000,
                },
            )
        call.invalidate_recordset(["artifact_ids"])
        artifact, legacy_artifact, deleted_user_artifact = call.artifact_ids.sorted("start_ms")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(legacy_response.status_code, 204)
        self.assertEqual(deleted_user_response.status_code, 204)
        self.assertEqual(len(call.artifact_ids), 3)
        self.assertEqual((artifact.start_ms, artifact.end_ms), (1_000, 3_000))
        self.assertTrue(artifact.is_stt)
        self.assertFalse(artifact.has_media_output)
        self.assertEqual(artifact.recording_started_by_id, recording_user)
        self.assertEqual(artifact.transcription_state, "pending")
        self.assertEqual(bytes(artifact.media_id.raw), b"audio")
        self.assertEqual(artifact.media_id.mimetype, "audio/ogg")
        self.assertTrue(legacy_artifact.has_media_output)
        self.assertFalse(legacy_artifact.recording_started_by_id)
        self.assertEqual(bytes(legacy_artifact.media_id.raw), b"legacy audio")
        self.assertFalse(deleted_user_artifact.recording_started_by_id)
        self.assertEqual(bytes(deleted_user_artifact.media_id.raw), b"deleted user audio")
        self.assertEqual(action_transcribe.call_count, 3)
        self.assertEqual(broadcast_recording.call_count, 3)
        call.invalidate_recordset(["has_audio", "has_recording", "has_video"])
        self.assertFalse(call.has_recording)
        self.assertFalse(call.has_audio)
        self.assertFalse(call.has_video)

    def test_transcribe_route_rejects_session_token(self):
        call_start = fields.Datetime.now()
        channel = self.env["discuss.channel"].create({"name": "Recorded Channel"})
        call = self.env["discuss.call.history"].create({
            "channel_id": channel.id,
            "start_dt": call_start,
        })
        token = jwt.sign(
            {
                "iat": int(datetime.now(UTC).timestamp()),
                "session_id": 1,
                "user_id": self.env.user.id,
            },
            discuss.get_derived_sfu_key(self.env, channel.id),
            ttl=60,
            algorithm=jwt.Algorithm.HS256,
        )
        response = self.url_open(
            f"/mail/rtc/recording/{call.id}/transcribe",
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "audio/ogg",
            },
            params={
                "start_ms": 1_000,
                "end_ms": 3_000,
                "has_media_output": "false",
            },
        )
        self.assertEqual(response.status_code, 404)
        call.invalidate_recordset(["artifact_ids"])
        self.assertFalse(call.artifact_ids)

    @mute_logger('odoo.http')
    def test_transcribe_endpoint_security(self):
        no_access_user = new_test_user(
            self.env,
            login='no_access_user',
            groups='base.group_portal'
        )
        private_channel = self.env['discuss.channel'].create({'name': 'Private Channel', 'channel_type': 'chat'})
        private_call = self.env['discuss.call.history'].create({
            'channel_id': private_channel.id,
            'start_dt': fields.Datetime.now(),
        })
        self.authenticate(no_access_user.login, no_access_user.login)
        with self.assertRaises(JsonRpcException, msg="odoo.exceptions.AccessError"):
            self.make_jsonrpc_request('/ai/transcription/call', {
                'call_model': 'discuss.call.history',
                'call_id': private_call.id,
            })

        user = new_test_user(
            self.env,
            login='standard_user',
            groups='base.group_user'
        )
        public_channel = self.env['discuss.channel'].create({
            'name': 'Public Channel',
            'channel_type': 'channel',
        })
        public_channel._add_members(partners=user.partner_id)
        public_call = self.env['discuss.call.history'].create({
            'channel_id': public_channel.id,
            'start_dt': fields.Datetime.now(),
        })
        artifact = self.env['mail.call.artifact'].sudo().create({
            'discuss_call_history_id': public_call.id,
            'start_ms': 0,
            'end_ms': 1000,
            'is_stt': True,
            'transcription_state': 'pending',
        })
        self.authenticate(user.login, user.login)
        with self.assertRaises(AccessError):
            artifact.with_user(user).write({'transcript': 'Hacker injection'})
        response = self.make_jsonrpc_request('/ai/transcription/call', {
            'call_model': 'discuss.call.history',
            'call_id': public_call.id,
        })
        self.assertEqual(response, "OK")
