from odoo import models


class PosConfig(models.Model):
    _inherit = "pos.config"

    def _load_self_data_models(self):
        return super()._load_self_data_models() + ['obox.obox']
