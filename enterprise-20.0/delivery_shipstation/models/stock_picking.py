# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ShipStation works based on internal label IDs rather than just tracking numbers.
    # So we need to store the associated label ID in conjunction with the tracking numbers
    # for getting tracking URLs or cancelling the individual picking.
    shipstation_label_ref = fields.Char("ShipStation Label Reference", copy=False)
