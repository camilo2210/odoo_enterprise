import logging

from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.exceptions import ConcurrencyError, UserError
from odoo.tools import BinaryBytes

_logger = logging.getLogger(__name__)


class VoipVoicemailMessage(models.Model):
    _name = "voip.voicemail.message"
    _description = "VoIP Mailbox Message"
    _order = "occurred_at desc, id desc"
    _rec_name = "pbx_message_id"

    event_id = fields.Char(required=True, readonly=True)
    pbx_message_id = fields.Char(string="PBX Message ID", required=True, readonly=True)
    voicemail_id = fields.Many2one(
        "voip.voicemail",
        string="Mailbox",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    occurred_at = fields.Datetime(readonly=True)
    caller_id_name = fields.Char(readonly=True)
    caller_id_num = fields.Char(string="Caller Number", readonly=True)
    duration = fields.Integer(readonly=True)
    is_empty = fields.Boolean(readonly=True)
    folder_name = fields.Char(readonly=True)
    folder_type = fields.Char(readonly=True)
    recording = fields.Binary(attachment=True, readonly=True)
    recording_filename = fields.Char(readonly=True)
    recording_version = fields.Integer(default=0, readonly=True)
    email_queued_at = fields.Datetime(readonly=True)
    raw_payload = fields.Json(readonly=True)

    _unique_event_id = models.UniqueIndex(
        "(event_id)", message="A mailbox message event is processed only once."
    )
    _unique_pbx_message_id = models.UniqueIndex(
        "(voicemail_id, pbx_message_id)", message="A PBX mailbox message can only be stored once."
    )

    @api.model
    def _handle_message_created_event(self, event_id, payload, occurred_at):
        payload = payload or {}
        # Both user_voicemail_message_created and global_voicemail_message_
        # created wrap the message under "message", with its ids duplicated
        # at the top level.
        message_payload = payload.get("message") or {}
        pbx_message_id = payload.get("message_id") or message_payload.get("id")
        pbx_voicemail_id = payload.get("voicemail_id") or (
            message_payload.get("voicemail") or {}
        ).get("id")
        if not event_id or not pbx_message_id or not pbx_voicemail_id:
            _logger.warning("Ignoring incomplete voicemail message event %s", event_id)
            return
        try:
            pbx_voicemail_id = int(pbx_voicemail_id)
        except (TypeError, ValueError):
            _logger.warning(
                "Ignoring voicemail message event %s with invalid voicemail ID %r",
                event_id, pbx_voicemail_id,
            )
            return
        voicemail = self.env["voip.voicemail"].sudo().search([
            ("pbx_voicemail_id", "=", pbx_voicemail_id),
        ], limit=1)
        if not voicemail:
            _logger.warning(
                "Ignoring voicemail message event %s for unknown PBX voicemail %s",
                event_id,
                pbx_voicemail_id,
            )
            return
        message = self._create_from_event(
            event_id,
            payload,
            message_payload,
            voicemail,
            pbx_message_id,
            occurred_at,
        )
        if message and not message.is_empty and not message.recording:
            message._fetch_recording_from_pbx()

    @api.model
    def _create_from_event(
        self,
        event_id,
        payload,
        message_payload,
        voicemail,
        pbx_message_id,
        occurred_at,
    ):
        existing_message = self.sudo().search([
            "|",
            ("event_id", "=", event_id),
            "&",
            ("voicemail_id", "=", voicemail.id),
            ("pbx_message_id", "=", pbx_message_id),
        ], limit=1)
        if existing_message:
            if existing_message.is_empty != bool(message_payload.get("empty")):
                existing_message.is_empty = bool(message_payload.get("empty"))
            return existing_message
        folder = message_payload.get("folder") or {}
        try:
            return self.sudo().create({
                "event_id": event_id,
                "pbx_message_id": pbx_message_id,
                "voicemail_id": voicemail.id,
                "occurred_at": occurred_at,
                "caller_id_name": message_payload.get("caller_id_name"),
                "caller_id_num": message_payload.get("caller_id_num"),
                "duration": int(message_payload.get("duration") or 0),
                "is_empty": bool(message_payload.get("empty")),
                "folder_name": folder.get("name"),
                "folder_type": folder.get("type"),
                "raw_payload": payload,
            })
        except UniqueViolation as e:
            raise ConcurrencyError() from e

    def _fetch_recording_from_pbx(self):
        for message in self.sudo():
            try:
                recording = message._get_pbx_recording()
            except (UserError, ValueError) as error:
                _logger.warning(
                    "Could not download PBX voicemail message recording %s: %s",
                    message.pbx_message_id,
                    error,
                )
                continue
            message.with_context(voip_skip_pbx_sync=True).write({
                "recording": BinaryBytes(recording["content"]),
                "recording_filename": message._get_recording_filename(recording),
                "recording_version": message.recording_version + 1,
            })
            message._send_recording_email()

    def _send_recording_email(self):
        """Queue the recording email once the PBX recording is available."""
        template = self.env.ref("voip.mail_template_voicemail_message")
        for message in self.sudo():
            recipient_email = message.voicemail_id._get_recipient_email()
            if (
                message.email_queued_at
                or not message.recording
                or not recipient_email
            ):
                continue
            template.send_mail(
                message.id,
                email_values={
                    "attachments": [(
                        message.recording_filename,
                        message.recording.content,
                    )],
                    "email_from": message.env.company.email_formatted,
                    "email_to": recipient_email,
                },
            )
            message.email_queued_at = fields.Datetime.now()

    def _get_pbx_recording(self):
        self.ensure_one()
        return self.env["voip.pbx.service"]._get_voicemail_message_recording(
            self.voicemail_id.pbx_voicemail_id,
            self.pbx_message_id,
        )

    def _get_recording_filename(self, recording):
        self.ensure_one()
        content_type = recording.get("mimetype") or ""
        mimetype = content_type.split(";", 1)[0].strip().lower()
        extension_by_mimetype = {
            "audio/mpeg": "mp3",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/webm": "webm",
        }
        if mimetype not in extension_by_mimetype:
            _logger.warning(
                "Unrecognized voicemail recording mimetype %r for message %s, defaulting to wav",
                mimetype,
                self.pbx_message_id,
            )
        extension = extension_by_mimetype.get(mimetype, "wav")
        return f"voicemail_{self.voicemail_id.pbx_voicemail_id}_{self.pbx_message_id}.{extension}"
