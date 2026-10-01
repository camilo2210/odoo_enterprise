# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    lazada_order_item_ids = fields.One2many(
        comodel_name="lazada.order.item", inverse_name="stock_move_id", string="Lazada Order Items"
    )

    def initialize_lazada_order_items(self):
        """Link Lazada order items from sale order lines to stock moves."""
        for move in self:
            move.lazada_order_item_ids = move.sale_line_id.lazada_order_item_ids
