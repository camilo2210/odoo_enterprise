from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_print_cmr(self):
        return self.env.ref('stock_fleet.action_report_cmr').report_action(self, config=False)
