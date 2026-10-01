from odoo import api, fields, models
from odoo.tools.sql import SQL


class DiscussCallHistory(models.Model):
    _name = "discuss.call.history"
    _inherit = ["discuss.call.history", "call.transcription.mixin"]

    has_transcript = fields.Boolean(
        compute="_compute_has_transcript",
        compute_sql="_compute_sql_has_transcript",
        compute_sudo=True,
    )

    @api.depends("artifact_ids.transcript")
    def _compute_has_transcript(self):
        for call in self:
            call.has_transcript = any(artifact.transcript for artifact in call.artifact_ids)

    def _compute_sql_has_transcript(self, table):
        artifact_fields = self.env["mail.call.artifact"]._fields
        return SQL(
            """EXISTS (
                SELECT 1
                FROM mail_call_artifact
                WHERE discuss_call_history_id = %s
                  AND transcript IS NOT NULL
                  AND transcript != ''
            )""",
            table.id,
            to_flush=(artifact_fields["discuss_call_history_id"], artifact_fields["transcript"]),
        )

    @api.depends("artifact_ids.is_stt")
    def _compute_recording_media(self):
        super()._compute_recording_media()

    def _after_artifact_transcription_done(self, artifact):
        super()._after_artifact_transcription_done(artifact)
        email_artifact = artifact
        if artifact.has_media_output:
            email_artifact = artifact._get_matching_recording_artifacts().filtered(
                lambda candidate: not candidate.is_stt
            )[:1]
        if email_artifact:
            email_artifact._send_recording_available_email()
