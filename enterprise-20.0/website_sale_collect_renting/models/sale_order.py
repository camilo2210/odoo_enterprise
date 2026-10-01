# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_insufficient_stock_data(self, wh_id, **kwargs):
        """Override of `website_sale_collect` to take rental dates into account."""
        return super()._get_insufficient_stock_data(
            wh_id,
            start_date=self.rental_start_date,
            end_date=self.rental_return_date,
            **kwargs
        )
