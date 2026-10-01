from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_voip_config(self) -> dict:
        provider = self.voip_provider_id
        return {**super()._get_voip_config(), "transcriptionPolicy": provider.transcription_policy or "disabled"}
