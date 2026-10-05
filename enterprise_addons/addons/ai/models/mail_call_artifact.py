import base64
import logging

from dateutil.relativedelta import relativedelta
from psycopg2.errors import LockNotAvailable, QueryCanceled  # noqa: OLS02001

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL

from odoo.addons.iap import InsufficientCreditError

from ..utils.ai_utils import call_odoo_ai

_logger = logging.getLogger(__name__)

# Based on OpenAI Transcriptions API limits https://platform.openai.com/docs/guides/speech-to-text#longer-inputs
TRANSCRIPTION_MAX_FILE_SIZE = 25 * 1024 * 1024


class MailCallArtifact(models.Model):
    _inherit = "mail.call.artifact"

    is_stt = fields.Boolean(
        string="Is STT Artifact", default=False,
        help="Indicates if this artifact is for Speech-to-Text (STT). "
             "If set, the media will be converted to a transcript."
    )
    transcription_state = fields.Selection(
        [
            ("pending", "Awaiting transcription"),
            ("done", "Done transcribing"),
            ("error", "Error, could not transcribe"),
        ],
        string="Transcription State",
        copy=False,
    )
    transcription_locked_until = fields.Datetime(copy=False, export_string_translation=False)
    transcription_error_count = fields.Integer(copy=False, default=0, export_string_translation=False)
    transcription_error_msg = fields.Char(copy=False, export_string_translation=False)
    transcript = fields.Text(string="Transcript (VTT)")
    has_media_output = fields.Boolean(copy=False)

    def _get_matching_recording_artifacts(self):
        self.ensure_one()
        return self._get_related_call().artifact_ids.filtered(
            lambda artifact: artifact.start_ms == self.start_ms and artifact.end_ms == self.end_ms
        )

    def _is_recording_available(self):
        self.ensure_one()
        if self.is_stt:
            return self.transcription_state == "done"
        return super()._is_recording_available() and all(
            artifact.transcription_state == "done"
            for artifact in self._get_matching_recording_artifacts()
            if artifact.is_stt
        )

    def _is_recording_media(self):
        self.ensure_one()
        return not self.is_stt and super()._is_recording_media()

    def _is_overlap_candidate(self):
        # Exclude STT artifacts from the standard media overlap check.
        # STT artifacts often contain internal timing cues (VTT/SRT) that can
        # offset the actual transcription content, making constraint unreliable
        return not self.is_stt and super()._is_overlap_candidate()

    def _get_transcription_queue_domain(self):
        """Return domain to find records to transcribe"""
        domain = Domain([
            ("transcription_state", "=", "pending"),
            ("is_stt", "=", True),
        ])
        is_unlocked = Domain("transcription_locked_until", "=", False)
        lock_expired = Domain("transcription_locked_until", "<=", fields.Datetime.now())
        domain &= (is_unlocked | lock_expired)
        if self:
            domain &= Domain('id', 'in', self.ids)
        return domain

    def _claim_records_to_transcribe(self, batch_size=None):
        """Phase 1 helper. Find pending records, claim them with a lease

        :return: list of leased records (record_id, lease_until) tuples
        """
        search_domain = self._get_transcription_queue_domain()

        # TX#1: claim (fast)
        # We use search() here instead of self.try_lock_for_update() directly to prevent
        # lock on the entire table if called on an empty recordset
        records = self.search(
            search_domain, order="create_date desc", limit=batch_size
        ).try_lock_for_update()
        if not records:
            return []

        lease_until = fields.Datetime.now() + relativedelta(minutes=15)
        records.sudo().write({"transcription_locked_until": lease_until})

        return [(rec.id, lease_until) for rec in records]

    def _is_lease_valid(self, lease_until):
        """Compare-And-Swap (CAS) guard. Check if the lease is still valid.

        `lease_until` acts as our unique token between phases.
        If the DB's `transcription_locked_until` has changed or expired,
        it means another worker or user stole/reset this record"""
        return (
            self.transcription_state == "pending"
            and self.transcription_locked_until == lease_until
            and self.transcription_locked_until > fields.Datetime.now()
        )

    def _transcribe_claimed_record(self, lease_until):
        """Phase 2 helper. Perform blocking IO (LLM API call) with NO WRITES to the DB.
        """
        self.ensure_one()

        if not self._is_lease_valid(lease_until):
            return {'status': 'skip'}

        if self.media_id.file_size > TRANSCRIPTION_MAX_FILE_SIZE:
            return {'status': 'file_too_large'}

        data = self.media_id.raw
        if not data:
            return {'status': 'no_media'}

        try:
            params = {
                'audio': base64.b64encode(data).decode('utf-8'),
                'response_format': 'vtt',
                'mimetype': self.media_id.mimetype,
            }
            text_vtt = call_odoo_ai(self.env, '1/get_transcription', params)['text']
            if text_vtt is None:
                return {'status': 'err'}
            return {'status': 'ok', 'transcript': text_vtt}

        except (InsufficientCreditError, UserError):
            _logger.error("Transcription attempt failed for call.artifact %s", self.id)
            return {'status': 'err'}

    def _after_transcription_done(self):
        for artifact in self:
            if artifact.is_stt and artifact.media_id:
                artifact.media_id.sudo().unlink()

            call = artifact._get_related_call()
            if call:
                call.sudo()._after_artifact_transcription_done(artifact)

    def _after_transcription_error(self):
        for artifact in self:
            call = artifact._get_related_call()
            if artifact.is_stt and artifact.media_id:
                _logger.info(
                    "Removing transcription artifact %s for %s(%s) "
                    "due to terminal error: %s",
                    artifact.id,
                    call._name if call else 'False',
                    call.id if call else 'False',
                    artifact.transcription_error_msg,
                )
                artifact.media_id.sudo().unlink()

            if call:
                call.sudo()._after_artifact_transcription_error(artifact)

    def _has_pending_stt_artifacts(self, call):
        """Check if the given call has any pending STT artifacts."""
        pending = call.artifact_ids.filtered(
            lambda a: a.is_stt and a.transcription_state == 'pending'
        )
        return bool(pending)

    def _finalize_transcription(self, lease_until, result, max_retries=5):
        """Phase 3 helper. Write results.

        :return: bool indicating if transcription was finalized
        """
        self.ensure_one()
        if not result or result.get('status') == 'skip':
            return False

        try:
            self.env.cr.execute("SET LOCAL lock_timeout = '3s'")
            self.env.cr.execute(SQL(
                'SELECT 1 FROM %s WHERE id=%s FOR UPDATE',
                SQL.identifier(self._table), self.id
            ))
        except (LockNotAvailable, QueryCanceled) as e:
            _logger.warning("Could not write transcription results: %s", e)
            return False

        if not self._is_lease_valid(lease_until):
            return False

        vals = {"transcription_locked_until": False}

        if result['status'] == "ok":
            vals.update({
                "transcript": result['transcript'],
                "transcription_state": "done",
                "transcription_error_count": 0,
                "transcription_error_msg": False,
            })
        elif result['status'] == "no_media":
            vals.update({
                "transcription_state": "error",
                "transcription_error_msg": "No media to transcribe",
            })
        elif result['status'] == "file_too_large":
            vals.update({
                "transcription_state": "error",
                "transcription_error_msg": "File too large for transcription",
            })
        elif result['status'] == "err":
            new_count = self.transcription_error_count + 1
            terminal = new_count >= max_retries
            vals.update({
                "transcription_error_count": new_count,
                "transcription_error_msg": "Transcription request failed",
                "transcription_state": "error" if terminal else "pending",
            })

        self.sudo().write(vals)

        if result['status'] == "ok":
            self._after_transcription_done()
        elif vals.get("transcription_state") == "error":
            self._after_transcription_error()

        call = self._get_related_call()
        if call and not self._has_pending_stt_artifacts(call):
            if any(a.transcription_state == "done" for a in call.artifact_ids if a.is_stt):
                call.sudo()._after_all_artifacts_transcribed()

        return True

    def action_transcribe_gevent(self):
        """Orchestrate the 3-phase transcription process for the recordset.

        WARNING: This method performs slow IO
        It must be called from a gevent-patched thread,
        NEVER from a standard synchronous action.
        """
        if not self:
            return

        # Phase 1: Claim batch (fast)
        claimed_records = self._claim_records_to_transcribe()
        # Factorized in the model to be reused by both VoIP and Discuss integrations.
        self.env.cr.commit()  # nosemgrep: commit-in-models

        for record_id, lease_until in claimed_records:
            record = self.browse(record_id)
            # Phase 2: Process (long IO, no lock)
            result = record._transcribe_claimed_record(lease_until)
            # Factorized in the model to be reused by both VoIP and Discuss integrations.
            self.env.cr.commit()  # nosemgrep: commit-in-models

            # Phase 3: Finalize (fast write)
            record._finalize_transcription(
                lease_until,
                result,
                max_retries=self.env["ir.config_parameter"].sudo().get_int("ai.max_transcription_retries", 5),
            )
            # Factorized in the model to be reused by both VoIP and Discuss integrations.
            self.env.cr.commit()  # nosemgrep: commit-in-models
