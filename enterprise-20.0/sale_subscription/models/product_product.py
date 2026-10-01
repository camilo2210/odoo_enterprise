# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.onchange('recurring_invoice')
    def _onchange_recurring_invoice(self):
        """
        Raise a warning if the user has checked 'Subscription Product'
        while the product has already been sold.
        In this case, the 'Subscription Product' field is automatically
        unchecked.
        """
        return self.product_tmpl_id._onchange_recurring_invoice()

    def _has_multiple_uoms(self):
        # multi-uoms doesn't work with subscription (for now)
        if self.recurring_invoice:
            return False
        return super()._has_multiple_uoms()
