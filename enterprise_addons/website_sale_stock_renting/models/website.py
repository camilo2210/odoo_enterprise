# Part of Odoo. See LICENSE file for full copyright and licensing details.

from zoneinfo import ZoneInfo

from odoo import models
from odoo.http import request


class Website(models.Model):
    _inherit = "website"

    def _get_product_available_qty(
        self, product, *, sale_order=None, start_date=None, end_date=None, **kwargs
    ):
        """Override of `website_sale_stock` to account for the rental period.

        :param sale_order: The sale order to compute the available quantity for.
        :param datetime start_date: The start of the rental period.
        :param datetime end_date: The end of the rental period.
        :param dict kwargs: Optional values
        :return: Available quantity
        :rtype: float
        """
        if product.rent_periodicity and product.is_storable:
            if not sale_order:
                sale_order = (
                    request.cart
                    if (request and hasattr(request, "cart"))
                    else self.env["sale.order"].sudo()
                )
            start_date, end_date = sale_order._get_default_rental_dates(
                product,
                start_date=start_date,
                end_date=end_date,
                tzinfo=ZoneInfo(self.tz) if self.tz else None,
            )
        return super()._get_product_available_qty(
            product, sale_order=sale_order, start_date=start_date, end_date=end_date, **kwargs
        )
