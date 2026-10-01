from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    obox_scale_id = fields.Many2one("obox.device", domain=lambda self: [('type', '=', 'scale')])
