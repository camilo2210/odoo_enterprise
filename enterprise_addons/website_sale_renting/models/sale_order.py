# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.date_utils import float_to_time, localized, to_timezone

from odoo.addons.sale_renting.const import SECONDS_IN_PERIODICITY


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_tzinfo(self):
        """Override to use the website timezone.

        When the order exists, use its website's timezone. Otherwise, use the current request
        website's timezone."""
        self.ensure_one()
        return (self.website_id and ZoneInfo(self.website_id.tz)) or super()._get_tzinfo()

    def _is_cart_ready_for_checkout(self, **kwargs):
        """Override of `website_sale` to check that the renting dates are still valid."""
        ready = super()._is_cart_ready_for_checkout(**kwargs)
        if not self.is_rental_order:
            return ready

        if error_msg := self._get_rental_dates_error_message():
            self._add_blocking_alert(error_msg)
            return False

        return ready

    def _get_rental_dates_error_base_message(self):
        """Return the generic error message prefix used when the rental dates are invalid."""
        return self.env._(
            "Some of your rental products cannot be rented during the selected period and your"
            " cart must be updated. We're sorry for the inconvenience."
        )

    def _get_rental_dates_error_message(self):
        """Return an error message if the rental dates are invalid, or an empty string if valid.

        :rtype: str
        """
        self.ensure_one()
        if not self.has_rentable_lines:
            return ""

        if not (self.rental_start_date and self.rental_return_date):
            return self.env._("No dates were specified on your rental order.")

        if self.rental_return_date <= self.rental_start_date:
            return self.env._("The return date should be after the pickup date.")

        invalid_qty_lines = self._get_rental_lines_below_minimum_qty()
        if invalid_qty_lines:
            return self.env._(
                "The selected rental period is too short for the quantity ordered"
                " of: %(products)s.",
                products=", ".join(invalid_qty_lines.product_id.mapped("name")),
            )

        base_msg = self._get_rental_dates_error_base_message()

        # 15 minutes of allowed time between adding the product to the cart and paying it
        now = fields.Datetime.now()
        if self.rental_start_date < now - timedelta(minutes=15):
            return base_msg + self.env._("\nYour rental product cannot be picked up in the past.")

        # RENTAL CALENDAR
        if calendar_sudo := self.company_id.sudo().rental_resource_calendar_id:
            tz_start_date = self._to_order_tz(self.rental_start_date)
            tz_return_date = self._to_order_tz(self.rental_return_date)
            # Avoid excluding interval limits
            interval_start = tz_start_date.replace(hour=0, minute=0, second=0)
            interval_end = tz_return_date.replace(hour=23, minute=59, second=59)
            intervals_dict = calendar_sudo._work_intervals_batch(interval_start, interval_end)
            intervals = intervals_dict.get(False, [])  # get intervals without specific resources

            # Hourly products must respect the hours of the calendar, other products, only the day
            hourly_products = all(
                product.rent_periodicity == "hours"
                for product in self.order_line.filtered("is_rental").product_id
            )
            if hourly_products:
                valid_start = any(start <= tz_start_date <= end for start, end, _ in intervals)
                valid_return = any(start <= tz_return_date <= end for start, end, _ in intervals)
            else:
                valid_start = any(
                    tz_start_date.date() == start.date() for start, end, _ in intervals
                )
                valid_return = any(
                    tz_return_date.date() == start.date() for start, end, _ in intervals
                )
            # Build the warning messages
            if not valid_start and not valid_return:
                return base_msg + self.env._(
                    "\nYour rental product's pickup (%(start_date)s) and return (%(end_date)s)"
                    " dates are invalid.",
                    start_date=self.rental_start_date,
                    end_date=self.rental_return_date,
                )
            if not valid_start:
                return base_msg + self.env._(
                    "\nYour rental product's pickup date (%(start_date)s) is invalid.",
                    start_date=self.rental_start_date,
                )
            if not valid_return:
                return base_msg + self.env._(
                    "\nYour rental product's return date (%(end_date)s) is invalid.",
                    end_date=self.rental_return_date,
                )

        return ""

    def _get_default_rental_dates(
        self, product_or_template, start_date=None, end_date=None, tzinfo=None
    ):
        if start_date and end_date:
            pass
        elif self.rental_start_date and self.rental_return_date:
            start_date = self.rental_start_date
            end_date = self.rental_return_date
        elif product_or_template.env.context.get(
            "start_date"
        ) and product_or_template.env.context.get("end_date"):
            start_date = product_or_template.env.context.get("start_date")
            end_date = product_or_template.env.context.get("end_date")
        else:
            template = (
                product_or_template.product_tmpl_id
                if product_or_template.is_product_variant
                else product_or_template
            )
            start_date, end_date = template._get_default_rental_dates(
                tzinfo=tzinfo or self._get_tzinfo()
            )
        return start_date, end_date

    def _get_rental_lines_below_minimum_qty(self):
        """Return the rental order lines whose quantity is below the minimum quantity required
        for the currently selected rental period.
        """
        return self.order_line.filtered(
            lambda line: (
                line.is_rental and line.order_id._get_remaining_minimum_qty(line.product_id) > 0
            )
        )

    def _get_minimum_rental_duration(self):
        """Return the rental duration threshold, for each rentable order line, above which the
        minimum quantity of that line's product is satisfied, regardless of the currently
        selected rental period.

        :return: The duration that must be exceeded (not reached) for the constraint to be
            satisfied, or `None` if there is no constraint.
        :rtype: timedelta | None
        """
        self.ensure_one()
        max_duration = None
        for product in self.order_line.filtered(lambda line: line.is_rental).product_id:
            periodicity = product.rent_periodicity
            if not (periodicity and product.minimum_quantity):
                continue
            cart_qty = self._get_cart_qty(product.id)
            if not cart_qty:
                continue
            periods_needed = math.ceil(product.minimum_quantity / cart_qty)
            duration = timedelta(seconds=(periods_needed - 1) * SECONDS_IN_PERIODICITY[periodicity])
            if max_duration is None or duration > max_duration:
                max_duration = duration
        return max_duration

    def _get_remaining_minimum_qty(self, product, exclude_line=None, uom=None):
        """Override to keep the remaining minimum quantity in sync for rental products."""
        if not product.rent_periodicity:
            return super()._get_remaining_minimum_qty(product, exclude_line=exclude_line, uom=uom)

        start_date = product.env.context.get("start_date") or self.rental_start_date
        end_date = product.env.context.get("end_date") or self.rental_return_date
        if not start_date or not end_date:
            return super()._get_remaining_minimum_qty(product, exclude_line=exclude_line, uom=uom)

        periods = product._get_number_of_periods(start_date, end_date)
        if periods == 0:
            remaining_qty = product.minimum_quantity
        else:
            cart_qty = self._get_cart_qty(product.id, exclude_line=exclude_line)
            remaining_qty = max(product.minimum_quantity / periods - cart_qty, 0)
        if uom and uom != product.uom_id:
            remaining_qty = product.uom_id._compute_quantity(remaining_qty, uom, round=False)
        return float_round(remaining_qty, precision_digits=0, rounding_method="UP")

    def _cart_add(self, product_id, *args, start_date=None, end_date=None, **kwargs):
        product = self.env["product.product"].browse(product_id)
        if product.rent_periodicity:
            dates_provided = start_date and end_date
            start_date, end_date = self._get_default_rental_dates(
                product, start_date=start_date, end_date=end_date
            )
            periodicity = product.rent_periodicity
            if dates_provided and periodicity != "hours" and self.website_id.tz:
                template = product.product_tmpl_id
                website_tz = ZoneInfo(self.website_id.tz)
                to_website_tz = to_timezone(website_tz)
                to_naive_utc = to_timezone(None)
                loc_start = to_website_tz(localized(start_date))
                loc_end = to_website_tz(localized(end_date))
                start_date = to_naive_utc(
                    datetime.combine(
                        loc_start, float_to_time(template.pickup_time), tzinfo=website_tz
                    )
                )
                end_date = to_naive_utc(
                    datetime.combine(
                        loc_end, float_to_time(template.return_time), tzinfo=website_tz
                    )
                )
            if (
                self.rental_start_date
                and self.rental_return_date
                and (self.rental_start_date != start_date or self.rental_return_date != end_date)
            ):
                raise UserError(
                    self.env._("You cannot mix different rental periods in the same order.")
                )
            self.update({
                "rental_start_date": start_date.replace(tzinfo=None),
                "rental_return_date": end_date.replace(tzinfo=None),
            })

        return super()._cart_add(
            product_id, *args, start_date=start_date, end_date=end_date, **kwargs
        )

    def _verify_cart_after_update(self, *args, **kwargs):
        super()._verify_cart_after_update(*args, **kwargs)
        if self.is_rental_order and not self.has_rentable_lines:
            self.write({"rental_start_date": False, "rental_return_date": False})

    def _is_renting_possible_in_hours(self):
        """Whether all products in the cart can be rented in a period computed in hours."""
        rental_order_lines = self.order_line.filtered("is_rental")
        return all(
            periodicity == "hours"
            for periodicity in rental_order_lines.product_id.mapped("rent_periodicity")
        )

    def _cart_update_renting_period(self, start_date, end_date) -> str:
        """Test and update the rental period if valid. If invalid, return a reason why without
        updating."""
        self.ensure_one()
        current_start_date = self.rental_start_date
        current_end_date = self.rental_return_date

        self.write({"rental_start_date": start_date, "rental_return_date": end_date})
        if error_msg := self._get_rental_dates_error_message():
            self.write({
                "rental_start_date": current_start_date,
                "rental_return_date": current_end_date,
            })
        else:
            rental_lines = self.order_line.filtered("is_rental")
            self.env.add_to_compute(rental_lines._fields["name"], rental_lines)
            self._recompute_rental_prices()

        return error_msg

    def _all_product_available(self):
        """Override to add the rental period in the context to compute product availabilities."""
        with_context = self
        if self.is_rental_order:
            with_context = self.with_context(
                start_date=self.rental_start_date, end_date=self.rental_return_date
            )
        return super(SaleOrder, with_context)._all_product_available()
