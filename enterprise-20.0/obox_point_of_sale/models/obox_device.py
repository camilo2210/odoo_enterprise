from odoo import api, models


class OboxDevice(models.Model):
    _name = "obox.device"
    _inherit = ["obox.device", "pos.load.mixin"]

    @api.model
    def _load_pos_data_fields(self, _config):
        return ["obox_id", "identifier"]
