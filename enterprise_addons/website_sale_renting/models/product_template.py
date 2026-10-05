# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import float_compare

from odoo.addons.sale_renting.const import SECONDS_IN_PERIODICITY


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_default_end_delta(self):
        """Override to extend the default rental duration, so that it already
        satisfies the product's minimum quantity for a single unit.
        """
        delta = super()._get_default_end_delta()
        if self.rent_periodicity and self.minimum_quantity > 1:
            delta += (self.minimum_quantity - 1) * timedelta(
                seconds=SECONDS_IN_PERIODICITY[self.rent_periodicity]
            )
        return delta

    def _get_additional_combination_info(
        self, product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
    ):
        """Override to add the information about renting for rental products.

        If the product is rentable, this override adds the following information about the rental:
            - is_rental: Whether a combination is rental,
            - rental_duration: The duration of the first defined product pricing on this product
            - rental_unit: The unit of the first defined product pricing on this product
            - default_start_date: If no pickup nor rental date in context, the start_date of the
                                   first renting sale order line in the cart;
            - default_end_date: If no pickup nor rental date in context, the end_date of the
                                   first renting sale order line in the cart;
            - base_unit_price: 0; Disabled.
            - base_unit_name: False; Disabled.
        """
        if not self.rent_periodicity:
            return super()._get_additional_combination_info(
                product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
            )

        order_sudo = (request and request.cart) or self.env["sale.order"].sudo()

        # Compute the default renting period of the product page (cart > context > defaults).
        tzinfo = ZoneInfo(website.tz)
        start_date, end_date = order_sudo._get_default_rental_dates(
            product_or_template,
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            tzinfo=tzinfo,
        )

        if start_date and end_date and start_date >= end_date:
            raise UserError(
                self.env._("Please choose a return date that is after the pickup date.")
            )

        res = super(
            ProductTemplate, self.with_context(start_date=start_date, end_date=end_date)
        )._get_additional_combination_info(
            product_or_template, quantity, uom, website, pricelist, fiscal_position, **kwargs
        )
        duration = self._get_number_of_periods(start_date, end_date)

        # The quantity stepper always starts at 1 for rental products: the minimum quantity
        # constraint is enforced through the rental duration instead.
        minimum_rental_qty = res.pop("minimum_qty", 1)
        res.pop("minimum_qty_reached_message", None)

        return {
            **res,
            "is_rental": bool(product_or_template.rent_periodicity),
            "minimum_rental_qty": minimum_rental_qty,
            "rental_duration": duration,
            "rental_unit": self._get_rent_periodicity_label(duration),
            "default_start_date": start_date,
            "default_end_date": end_date,
            #  Disable base unit prices logic for rental products
            "base_unit_price": 0,
            "base_unit_name": False,
        }

    def _get_price_before_discount(
        self, pricelist_item, pricelist_price, product_or_template, quantity, uom, currency
    ):
        """Override of `website_sale` to work with rental products.

        Rental prices are computed by aggregating every pricelist rule applicable across the
        rental period (see ``ProductPricelist._compute_rental_price_rule``), so no single rule
        can represent the whole price. Because of that,  ``pricelist_item._show_discount_on_shop()``
        always returns ``False`` for an empty recordset, the generic ``_get_price_before_discount``
        can never detect a discount for rental products, hence this override.
        """
        if not self.rent_periodicity:
            return super()._get_price_before_discount(
                pricelist_item, pricelist_price, product_or_template, quantity, uom, currency
            )
        return self.env["product.pricelist"]._get_product_price(
            product_or_template, quantity=quantity, uom=uom, currency=currency
        )

    def _search_render_results_prices(self, mapping, combination_info):
        if not combination_info.get("is_rental"):
            return super()._search_render_results_prices(mapping, combination_info)

        duration = combination_info["rental_duration"]
        unit = combination_info["rental_unit"]

        website = self.env.website
        return website._render_template(
            "website_sale_renting.rental_search_result_price",
            values={
                "currency": mapping["search_item_metadata"]["display_currency"],
                "price": combination_info["price"],
                "duration": duration,
                "unit": unit,
            },
        )

    def _get_sales_prices(self, pricelist_sudo, fiscal_position_sudo, website):
        prices = super()._get_sales_prices(pricelist_sudo, fiscal_position_sudo, website)
        start_date = self.env.context.get("start_date")
        end_date = self.env.context.get("end_date")
        for template in self:
            if not template.rent_periodicity:
                continue

            duration = 1
            if start_date and end_date:
                duration = template._get_number_of_periods(start_date, end_date)

            prices[template.id]["rental_duration"] = duration
            prices[template.id]["rental_unit"] = template._get_rent_periodicity_label(duration)

        return prices

    def _search_get_detail(self, website, order, options):
        search_details = super()._search_get_detail(website, order, options)
        if options.get("rent_only") or (options.get("from_date") and options.get("to_date")):
            search_details["base_domain"].append([("rent_periodicity", "!=", False)])
        return search_details

    # TODO provide a way to return error message instead, cause 'product doesn't exist' isn't really
    # understandable.
    def _is_purchasable(self, product=None) -> bool:
        # Override of `website_sale` to handle rental products
        if not super()._is_purchasable(product):
            return False

        if (
            not self.rent_periodicity
            or not (cart := request.cart)
            or not (cart.rental_start_date and cart.rental_return_date)
        ):
            # Not a rental product, no cart, or no rentals in the current cart
            return True

        rental_lines = cart.order_line.filtered("is_rental")
        if rental_lines and (
            rental_lines.product_id == product or rental_lines.product_template_id == self
        ):
            # Only rental product in cart is the current product so we allow any period change
            return True

        if self.rent_periodicity == "hours":
            return True

        # Only allow if the order pickup & return times match the product pickup & return times.
        pickup_time, return_time = self.pickup_time, self.return_time
        loc_pickup_date, loc_return_date = (
            cart._to_order_tz(cart.rental_start_date),
            cart._to_order_tz(cart.rental_return_date),
        )

        return not (
            float_compare(loc_pickup_date.hour + loc_pickup_date.minute / 60, pickup_time, 2)
            or float_compare(loc_return_date.hour + loc_return_date.minute / 60, return_time, 2)
        )
