from json.decoder import JSONDecodeError
from logging import getLogger
import re

from requests.exceptions import RequestException

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.ai.utils.ai_utils import get_text_from_parts
from odoo.addons.mail.tools.discuss import Store
from odoo.tools.sql import SQL

_logger = getLogger(__name__)


class VoipCall(models.Model):
    _name = "voip.call"
    _explanation = "Extends VoIP calls, providing call transcription capabilities using AI services."
    _inherit = ["voip.call", "call.transcription.mixin"]

    summary = fields.Char(string="Summary", copy=False)
    is_summary_visible = fields.Boolean(
        compute="_compute_is_summary_visible",
        export_string_translation=False,
    )
    has_transcript = fields.Boolean(compute="_compute_has_transcript", compute_sql="_compute_sql_has_transcript", compute_sudo=True)
    transcription_state = fields.Selection(
        [
            ("pending", "Awaiting transcription"),
            ("done", "Done transcribing"),
            ("error", "Error, could not transcribe"),
        ],
        string="Transcription State",
        compute="_compute_transcription_state",
        compute_sql="_compute_sql_transcription_state",
        compute_sudo=True,
    )

    @api.depends("artifact_ids.transcription_state")
    def _compute_transcription_state(self):
        for call in self:
            states = set(call.artifact_ids.mapped("transcription_state"))
            valid_states = {s for s in states if s}

            if "pending" in valid_states:
                call.transcription_state = "pending"
            elif "error" in valid_states:
                call.transcription_state = "error"
            elif "done" in valid_states:
                call.transcription_state = "done"
            else:
                call.transcription_state = False

    def _compute_sql_transcription_state(self, table):
        return SQL(
            """(
                SELECT transcription_state
                FROM mail_call_artifact
                WHERE voip_call_id = %s
                ORDER BY (
                    CASE transcription_state
                        WHEN 'pending' THEN 1
                        WHEN 'error' THEN 2
                        WHEN 'done' THEN 3
                        ELSE 4
                    END
                )
                LIMIT 1
            )""",
            table.id,
        )

    @api.depends("summary", "transcription_state")
    def _compute_is_summary_visible(self):
        is_admin = self.env.user.has_group("voip.group_voip_admin")
        for call in self:
            if is_admin:
                call.is_summary_visible = bool(call.transcription_state)
            else:
                call.is_summary_visible = bool(call.summary)

    @api.depends("artifact_ids")
    def _compute_has_recording(self):
        # OVERRIDE: STT transcripts are artifacts but should not trigger the 'recording' icon.
        for call in self:
            call.has_recording = any(not art.is_stt for art in call.artifact_ids)

    def _compute_sql_has_recording(self, table):
        # OVERRIDE: STT transcripts are artifacts but should not trigger the 'recording' icon.
        return SQL(
            "EXISTS (SELECT 1 FROM mail_call_artifact WHERE voip_call_id = %s AND (is_stt IS NULL OR is_stt = FALSE))",
            table.id,
        )

    @api.depends("artifact_ids.transcript")
    def _compute_has_transcript(self):
        for call in self:
            call.has_transcript = any(art.transcript for art in call.artifact_ids)

    def _compute_sql_has_transcript(self, table):
        return SQL(
            "EXISTS (SELECT 1 FROM mail_call_artifact WHERE voip_call_id = %s AND transcript IS NOT NULL AND transcript != '')",
            table.id,
        )

    def _after_all_artifacts_transcribed(self):
        # Generate summary
        summary = self._generate_call_summary()
        if self.user_id:
            self.user_id.partner_id._bus_send('simple_notification', {
                'title': self.env._('Transcription Completed'),
                'message': self.env._(' "%s"', summary) if summary else "",
                'type': 'success',
            })
        self.update_activity_message()

    def update_activity_message(self):
        for call in self:
            if call.activity_id and not call.activity_id.feedback and call.summary:
                call.activity_id.feedback = call.summary
        return super().update_activity_message()

    def _generate_call_summary(self):
        # Generate one-liner summary from concatenated transcripts
        summary_response = []
        try:
            ai_agent = self.env.ref('voip_ai.voip_call_summary_agent', raise_if_not_found=False)
            if not ai_agent:
                return ""
            full_transcript = "\n".join(art.transcript for art in self.artifact_ids if art.transcript)
            if full_transcript:
                clean_transcript = re.sub(r'</?transcript>', '', full_transcript, flags=re.IGNORECASE)
                ai_message = [{'type': 'text', 'text': f"<transcript>\n{clean_transcript}\n</transcript>"}]
                ai_response_message = ai_agent._generate_single_response(message=ai_message)
                if summary_response := get_text_from_parts(ai_response_message):
                    self.summary = summary_response
        except (RequestException, JSONDecodeError, UserError):
            _logger.error("Call %s: one-liner summary generation failed", self.id)
        return self.summary if self.summary else ""

    def _store_voip_fields(self, res: Store.FieldList):
        super()._store_voip_fields(res)
        res.extend(["has_transcript", "transcription_state"])
