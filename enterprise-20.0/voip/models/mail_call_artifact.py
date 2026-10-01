import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailCallArtifact(models.Model):
    _inherit = "mail.call.artifact"

    voip_call_id = fields.Many2one("voip.call", string="VoIP Call", ondelete="cascade", index=True)

    _artifact_has_possessor = models.Constraint(
        "CHECK(num_nonnulls(discuss_call_history_id, voip_call_id) = 1)",
        "Artifact must be linked to exactly one call source (Discuss or VoIP)."
    )

    def _get_related_call(self):
        self.ensure_one()
        return self.voip_call_id or super()._get_related_call()

    @api.autovacuum
    def _gc_demo_recordings(self):
        """Delete demo recordings older than 1 day to prevent server storage abuse."""
        if not self.env["voip.provider"].search_count([("mode", "=", "demo")], limit=1):
            return
        self.search([
            ("create_date", "<", "-1d"),
            ("voip_call_id.is_production", "=", False),
        ]).unlink()

    @api.constrains("start_ms", "end_ms", "discuss_call_history_id", "voip_call_id")
    def _constrains_artifacts_overlap(self):
        super()._constrains_artifacts_overlap()

    def _get_artifacts_grouped_by_call(self):
        grouped = super()._get_artifacts_grouped_by_call()
        voip_artifacts = self.voip_call_id.artifact_ids
        if voip_artifacts:
            grouped.update(voip_artifacts.grouped('voip_call_id'))
        return grouped
