# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class SaleReport(models.Model):
    _inherit = 'sale.report'

    def _order_line_domain(self):
        # Do not add upsell information to the sales report
        # as it will be updated on the original sale order.
        # Note: this analysis may not be accurate because
        # it does not take account of discounts, for example.
        return super()._order_line_domain() & (
            Domain('order_id.subscription_state', '=', False)
            | (Domain('product_id.recurring_invoice', '=', False) & Domain('order_id.subscription_state', '=', '7_upsell'))
            | Domain('order_id.subscription_state', '!=', '7_upsell')
        )
