from collections import defaultdict

from odoo import models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _action_done(self):
        res = super()._action_done()
        lots_per_order = defaultdict(lambda: self.env['stock.lot'])
        for move_line in self.exists():
            if not move_line.lot_id or move_line.location_dest_id.usage != 'customer':
                continue
            order = move_line.move_id.sale_line_id.order_id
            if order:
                lots_per_order[order] |= move_line.lot_id

        for order, delivered_lots in lots_per_order.items():
            for line in order.order_line.filtered('allow_lot_update'):
                line.lot_ids |= delivered_lots
        return res
