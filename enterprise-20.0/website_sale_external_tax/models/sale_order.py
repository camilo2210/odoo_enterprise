# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _recompute_taxes(self):
        super()._recompute_taxes()
        if self.env.context.get("recompute_external_taxes"):
            self._get_and_set_external_taxes_on_eligible_records()

    def _update_cart_taxes_and_prices(self):
        """Override of `website_sale` to ensure external taxes are computed without errors."""
        try:
            return super(
                SaleOrder, self.with_context(recompute_external_taxes=True)
            )._update_cart_taxes_and_prices()
        except UserError as exc:
            self._add_blocking_alert(
                self.env._(
                    "Your address does not appear to be valid. Please make sure it has been filled"
                    " in correctly.\n\nError details: %(error)s",
                    error=str(exc),
                )
            )
            return True
