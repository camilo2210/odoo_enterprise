# Part of Odoo. See LICENSE file for full copyright and licensing details.

from zoneinfo import ZoneInfo

from odoo import models
from odoo.http import request


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_additional_combination_info(
        self, product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
    ):
        """Override of `website_sale_collect` to pass the rental dates."""
        if not product_or_template.rent_periodicity:
            return super()._get_additional_combination_info(
                product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
            )

        order_sudo = (
            request.cart
            if (request and hasattr(request, "cart"))
            else self.env["sale.order"].sudo()
        )
        start_date, end_date = order_sudo._get_default_rental_dates(
            product_or_template, tzinfo=ZoneInfo(website.tz)
        )
        return super()._get_additional_combination_info(
            product_or_template,
            quantity,
            uom,
            website,
            pricelist,
            fiscal_position,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )
