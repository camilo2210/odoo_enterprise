from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_obox_scale_id = fields.Many2one(related="pos_config_id.obox_scale_id", readonly=False)
