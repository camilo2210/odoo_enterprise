from unittest.mock import patch

from odoo import fields
from odoo.tools import mute_logger

from odoo.addons.voip.tests.common_voip import VoipPhoneServiceCase


def _message_payload(event_id, voicemail_id, message_id, **overrides):
    message = {
        "id": message_id,
        "caller_id_name": "Jane Doe",
        "caller_id_num": "+32485000001",
        "duration": 12,
        "empty": False,
        "folder": {"name": "INBOX", "type": "old"},
        **overrides,
    }
    return event_id, {
        "voicemail_id": voicemail_id,
        "message_id": message_id,
        "message": message,
    }


class TestVoipVoicemailMessage(VoipPhoneServiceCase):
    def _create_mailbox(self, **values):
        return self.env["voip.voicemail"].with_context(voip_skip_pbx_sync=True).create({
            "name": "Support",
            "email": "support@example.com",
            "pbx_voicemail_id": 555,
            **values,
        })

    def test_message_created_event_creates_message_and_fetches_recording(self):
        mailbox = self._create_mailbox()
        event_id, payload = _message_payload("evt-1", mailbox.pbx_voicemail_id, "msg-1")

        self.env["voip.voicemail.message"]._handle_message_created_event(
            event_id, payload, fields.Datetime.now(),
        )

        message = self.env["voip.voicemail.message"].search([("event_id", "=", "evt-1")])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.voicemail_id, mailbox)
        self.assertEqual(message.caller_id_name, "Jane Doe")
        self.assertEqual(message.caller_id_num, "+32485000001")
        self.assertEqual(message.duration, 12)
        self.assertFalse(message.is_empty)
        self.assertEqual(message.folder_name, "INBOX")
        self.assertEqual(message.folder_type, "old")
        self.assertTrue(message.recording)
        self.assertEqual(message.recording_filename, "voicemail_555_msg-1.wav")
        self.assertEqual(message.recording_version, 1)
        self.assertTrue(message.email_queued_at)

    def test_message_created_event_is_idempotent_on_the_same_event_id(self):
        mailbox = self._create_mailbox()
        event_id, payload = _message_payload("evt-2", mailbox.pbx_voicemail_id, "msg-2")

        self.env["voip.voicemail.message"]._handle_message_created_event(
            event_id, payload, fields.Datetime.now(),
        )
        self.env["voip.voicemail.message"]._handle_message_created_event(
            event_id, payload, fields.Datetime.now(),
        )

        self.assertEqual(
            self.env["voip.voicemail.message"].search_count([("event_id", "=", event_id)]), 1,
        )

    def test_empty_message_does_not_fetch_a_recording(self):
        mailbox = self._create_mailbox()
        event_id, payload = _message_payload(
            "evt-3", mailbox.pbx_voicemail_id, "msg-3", empty=True,
        )

        self.env["voip.voicemail.message"]._handle_message_created_event(
            event_id, payload, fields.Datetime.now(),
        )

        message = self.env["voip.voicemail.message"].search([("event_id", "=", event_id)])
        self.assertTrue(message.is_empty)
        self.assertFalse(message.recording)
        self.assertFalse(message.email_queued_at)

    def test_recording_filename_uses_known_extension(self):
        mailbox = self._create_mailbox()
        message = self.env["voip.voicemail.message"].sudo().create({
            "event_id": "evt-4",
            "pbx_message_id": "msg-4",
            "voicemail_id": mailbox.id,
            "occurred_at": fields.Datetime.now(),
        })

        self.assertEqual(
            message._get_recording_filename({"mimetype": "audio/mpeg"}), "voicemail_555_msg-4.mp3",
        )
        self.assertEqual(
            message._get_recording_filename({"mimetype": "audio/x-wav"}), "voicemail_555_msg-4.wav",
        )

    @mute_logger("odoo.addons.voip.models.voip_voicemail_message")
    def test_recording_filename_defaults_to_wav_for_unknown_mimetype(self):
        mailbox = self._create_mailbox()
        message = self.env["voip.voicemail.message"].sudo().create({
            "event_id": "evt-5",
            "pbx_message_id": "msg-5",
            "voicemail_id": mailbox.id,
            "occurred_at": fields.Datetime.now(),
        })

        self.assertEqual(
            message._get_recording_filename({"mimetype": "audio/unknown"}), "voicemail_555_msg-5.wav",
        )

    def test_send_recording_email_does_not_requeue_once_sent(self):
        mailbox = self._create_mailbox()
        event_id, payload = _message_payload("evt-6", mailbox.pbx_voicemail_id, "msg-6")
        self.env["voip.voicemail.message"]._handle_message_created_event(
            event_id, payload, fields.Datetime.now(),
        )
        message = self.env["voip.voicemail.message"].search([("event_id", "=", event_id)])
        self.assertTrue(message.email_queued_at)

        with patch(
            "odoo.addons.mail.models.mail_template.MailTemplate.send_mail",
        ) as send_mail:
            message._send_recording_email()

        send_mail.assert_not_called()

    def test_send_recording_email_is_skipped_without_a_recipient_email(self):
        mailbox = self._create_mailbox(email=False)
        event_id, payload = _message_payload("evt-7", mailbox.pbx_voicemail_id, "msg-7")

        self.env["voip.voicemail.message"]._handle_message_created_event(
            event_id, payload, fields.Datetime.now(),
        )

        message = self.env["voip.voicemail.message"].search([("event_id", "=", event_id)])
        self.assertTrue(message.recording)
        self.assertFalse(message.email_queued_at)
