from odoo import models
from odoo.fields import Command


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _should_ignore_backorders(self):
        return super()._should_ignore_backorders() and not any(
            move.sale_line_id.is_rental for move in self.move_ids
        )

    def _create_return(self):
        return_picking = super()._create_return()
        return_picking.move_ids = [Command.delete(m.id) for m in return_picking.move_ids.filtered(lambda m: m.sale_line_id.is_rental)]
        return return_picking
