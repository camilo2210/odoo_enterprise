from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _should_reset_under_warranty(self):
        return super()._should_reset_under_warranty() and not self.recurring_invoice
