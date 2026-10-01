from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_self_ordering_obox_id = fields.Many2one(
        related="pos_config_id.self_ordering_obox_id",
        domain="[('supports_kiosk', '=', True)]",
        readonly=False,
    )
