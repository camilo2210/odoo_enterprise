from odoo import models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def action_print_cmr_batch(self):
        return self.env.ref('stock_fleet.action_report_cmr_batch').report_action(self, config=False)
