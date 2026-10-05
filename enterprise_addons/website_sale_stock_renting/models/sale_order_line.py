# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import format_datetime, format_time


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_shop_warning_stock(self, desired_quantity, available_quantity):
        """Adapt availability message for rental products."""
        self.ensure_one()
        if not self.is_rental:
            return super()._get_shop_warning_stock(desired_quantity, available_quantity)

        return self.env._(
            "You requested %(desired_quantity)g %(product_name)s, but only %(available_quantity)g"
            " are available from %(rental_period)s.",
            desired_quantity=desired_quantity,
            product_name=self.product_id.name,
            available_quantity=available_quantity,
            rental_period=self._get_rental_period_description(),
        )

    def _get_rental_period_description(self):
        self.ensure_one()
        order_tz = str(self.order_id._get_tzinfo())
        to_order_tz = self.order_id._to_order_tz

        start_date_part = format_datetime(self.env, self.start_date, tz=order_tz, dt_format="short")
        if to_order_tz(self.start_date).date() == to_order_tz(self.return_date).date():
            # If return day is the same as pickup day, don't display return_date Y/M/D in
            # description.
            return_date_part = format_time(
                self.env, self.return_date, tz=order_tz, time_format="short"
            )
        else:
            return_date_part = format_datetime(
                self.env, self.return_date, tz=order_tz, dt_format="short"
            )

        timezone_part = ""
        website = self.order_id.website_id
        if website and not website._is_customer_in_the_same_timezone():
            timezone_part = f" ({order_tz})"

        return self.env._(
            "%(from_date)s to %(to_date)s%(timezone)s",
            from_date=start_date_part,
            to_date=return_date_part,
            timezone=timezone_part,
        )
