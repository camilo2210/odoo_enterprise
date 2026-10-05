# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    iot_scale_ids = fields.Many2many(
        'iot.device',
        string="Scales",
        domain=[('type', '=', 'scale')],
        help=(
            "Choose the scales you want to use for this operation type. "
            "Those scales can be used to weigh the packages created."
        ),
    )
