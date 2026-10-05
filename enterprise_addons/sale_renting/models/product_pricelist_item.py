# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    def _compute_price(self, product, *args, start_date=None, end_date=None, depth=0, **kwargs):
        """Override of `product` to multiply prices by the number of periods for rentals.

        :param datetime start_date: The beginning of the rental period.
        :param datetime end_date: The end of the rental period.
        :param int depth: Technical flag to avoid multiplying the computed price twice with the
            number of periods. seealso:`_compute_base_price`.
        """
        res = super()._compute_price(
            product, *args, start_date=start_date, end_date=end_date, depth=depth, **kwargs
        )
        # Ensure the base pricelist's price doesn't multiply twice with the number of periods
        if not depth and product.rent_periodicity and start_date and end_date:
            res *= product._get_number_of_periods(start_date, end_date)

        return res

    def _compute_price_before_discount(self, *args, start_date=None, end_date=None, **kwargs):
        """Override to extend the kwargs using the rental context."""
        start_date = start_date or self.env.context.get("start_date")
        end_date = end_date or self.env.context.get("end_date")
        return super()._compute_price_before_discount(
            *args, start_date=start_date, end_date=end_date, **kwargs
        )
