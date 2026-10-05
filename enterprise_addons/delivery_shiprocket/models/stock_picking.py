# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    eway_bill_number = fields.Char("EWay Bill", copy=False)
    shiprocket_orders = fields.Char(
        string="Shiprocket Order(s)",
        copy=False, readonly=True,
        help="Store shiprocket order(s) in a (+) separated string, used in cancelling the order."
    )
    shiprocket_courier_name = fields.Char(
        string="Shiprocket Courier",
        copy=False, readonly=True,
        help="The actual courier name assigned by Shiprocket for this shipment."
    )

    def _get_carrier_name(self):
        """Override of stock_delivery to return the actual courier name for Shiprocket shipments."""
        if self.carrier_id.delivery_type == 'shiprocket' and self.shiprocket_courier_name:
            return self.shiprocket_courier_name
        return super()._get_carrier_name()
