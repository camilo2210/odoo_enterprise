# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import UTC, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_amount
from odoo.tools.date_utils import float_to_time, to_timezone

from odoo.addons.sale_renting import const, utils


class ProductTemplate(models.Model):
    _inherit = "product.template"

    rent_periodicity = fields.Selection(
        string="Rental Periodicity",
        selection=[("hours", "Hours"), ("days", "Days"), ("nights", "Nights"), ("weeks", "Weeks")],
    )
    pickup_time = fields.Float(
        default=lambda self: (self.env.context.get("default_rent_periodicity") and 9) or 0
    )
    return_time = fields.Float(
        default=lambda self: (self.env.context.get("default_rent_periodicity") and 18) or 0
    )

    qty_in_rent = fields.Float("Quantity currently in rent", compute="_compute_qty_in_rent")
    display_price = fields.Char(string="Rental price", compute="_compute_display_price")

    _check_24h_pickup_and_return_time = models.Constraint(
        "CHECK (0 <= pickup_time AND pickup_time < 24 AND 0 <= return_time AND return_time < 24)",
        "The pickup and return time must be between 0 and 24h (not included).",
    )
    _check_pickup_return_time_nights = models.Constraint(
        """CHECK (NOT (rent_periodicity = 'nights' AND pickup_time < return_time))""",
        "For nightly rentals, the pickup time must be later than the return time.",
    )

    def _compute_display_price(self):
        rental_products = self.filtered("rent_periodicity")
        (self - rental_products).display_price = ""
        for product in rental_products:
            product.display_price = (
                f"{format_amount(self.env, product.list_price, product.currency_id)}"
                f" / {product._get_rent_periodicity_label()}"
            )

    def _compute_qty_in_rent(self):
        rentable = self.filtered("rent_periodicity")
        not_rentable = self - rentable
        not_rentable.update({"qty_in_rent": 0.0})
        for template in rentable:
            template.qty_in_rent = sum(template.mapped("product_variant_ids.qty_in_rent"))

    @api.constrains("type", "combo_ids", "rent_periodicity")
    def _check_rental_combo_ids(self):
        for template in self:
            if (
                template.type == "combo"
                and template.rent_periodicity
                and not all(
                    product.rent_periodicity == template.rent_periodicity
                    for product in template.combo_ids.combo_item_ids.product_id
                )
            ):
                raise ValidationError(
                    template.env._(
                        "A rental combo product can only contain rental products with the same"
                        " periodicity."
                    )
                )

    @api.onchange("rent_periodicity")
    def _onchange_rent_periodicity(self):
        """Swap pickup time and return time when swapping to and from nights or weeks
        periodicity."""
        for template in self:
            if not (
                (template.rent_periodicity in {"nights", "weeks"})
                ^ (template.pickup_time < template.return_time)
            ):
                template.pickup_time, template.return_time = (
                    template.return_time,
                    template.pickup_time,
                )

    @api.model
    def _get_incompatible_types(self):
        return ["rent_periodicity"] + super()._get_incompatible_types()

    def action_view_rentals(self):
        """Access Schedule view of rental order lines, filtered on variants of the current
        templates."""
        return self.product_variant_ids.action_view_rentals()

    @api.depends("rent_periodicity")
    @api.depends_context("show_rental_tag")
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get("show_rental_tag"):
            return
        for template in self:
            if template.rent_periodicity:
                template.display_name = template.env._("%s (Rental)", template.display_name)

    def _get_rent_periodicity_label(self, duration=1, /):
        self.ensure_one()
        if duration <= 1:
            return const.PERIODICITY_LABEL_SINGULAR[self.rent_periodicity]
        return const.PERIODICITY_LABEL[self.rent_periodicity]

    @api.model
    def _get_additional_configurator_data(
        self,
        product_or_template,
        date,
        currency,
        pricelist,
        *,
        start_date=None,
        end_date=None,
        **kwargs,
    ):
        """Override of `sale` to append rental data.

        :param product.product|product.template product_or_template: The product for which to get
            additional data.
        :param datetime date: The date to use to compute prices.
        :param res.currency currency: The currency to use to compute prices.
        :param product.pricelist pricelist: The pricelist to use to compute prices.
        :param datetime|None start_date: The rental start date, to compute the rental duration.
        :param datetime|None end_date: The rental end date, to compute the rental duration.
        :param dict kwargs: Locally unused data passed to `super`.
        :rtype: dict
        :return: A dict containing additional data about the specified product.
        """
        data = super()._get_additional_configurator_data(
            product_or_template,
            date,
            currency,
            pricelist,
            start_date=start_date,
            end_date=end_date,
            **kwargs,
        )
        # TODO LIPI: don't show periodicity_label if has_rentable_lines but not period
        if not product_or_template.rent_periodicity:
            return data

        duration = 1
        if start_date and end_date:
            duration = product_or_template._get_number_of_periods(start_date, end_date)
        template = (
            product_or_template.product_tmpl_id
            if product_or_template.is_product_variant
            else product_or_template
        )
        periodicity_label = template._get_rent_periodicity_label(duration)
        data["price_info"] = (
            f"/ {duration} {periodicity_label}" if duration > 1 else f"/ {periodicity_label}"
        )
        return data

    def _has_multiple_uoms(self):
        # multi-uoms doesn't work with rental (for now)
        if self.rent_periodicity:
            return False
        return super()._has_multiple_uoms()

    def _get_number_of_periods(self, start_date, end_date):
        return utils.number_of_periods(self.rent_periodicity, start_date, end_date)

    def _get_default_rental_dates(self, *, tzinfo=None):
        """Get default renting dates to help user.

        Note: `self and self.ensure_one()`

        :param ZoneInfo tzinfo: The timezone in which the product is rented, default to UTC
        :return: The default start and end datetime in naive UTC.
        :rtype: tuple[datetime, datetime]
        """
        if self:
            self.ensure_one()

        to_sales_tz = to_timezone(tzinfo or UTC)
        to_naive_utc = to_timezone(None)

        def combine_with_hour(dt, hour_):
            if self.rent_periodicity not in {"hours", False}:
                return datetime.combine(dt, float_to_time(hour_), tzinfo=dt.tzinfo)
            return dt

        loc_now = to_sales_tz(fields.Datetime.now().replace(minute=0, second=0))
        loc_start_date = loc_now + self._get_default_start_delta()
        loc_start_date = self._get_first_potential_date(loc_start_date)
        loc_start_date = combine_with_hour(loc_start_date, self.pickup_time)

        loc_end_date = loc_start_date + self._get_default_end_delta()
        loc_end_date = self._get_first_potential_date(loc_end_date)
        loc_end_date = combine_with_hour(loc_end_date, self.return_time)

        return to_naive_utc(loc_start_date), to_naive_utc(loc_end_date)

    def _get_default_start_delta(self):
        if self.rent_periodicity not in {"hours", False}:
            return timedelta(days=1)
        return timedelta(hours=1)

    def _get_default_end_delta(self):
        if unit := self.rent_periodicity:
            if unit == "days" and self.pickup_time < self.return_time:
                # Ensure period defaults to 1 day after return_time is applied.
                return timedelta(days=0)
            if unit == "weeks" and self.pickup_time < self.return_time:
                # Ensure period defaults to 1 week after return_time is applied.
                return timedelta(days=6)
            if unit == "nights":
                unit = "days"
            return timedelta(**{unit: 1})
        return timedelta(days=1)

    def _get_first_potential_date(self, date):
        """Offset to the first potential date which respects the rental calendar.
        :param datetime date: The localized datetime we want to verify.
        :rtype: Datetime
        :return: The first datetime matching the rental calendar, if any.
        """
        calendar_sudo = self.env.company.sudo().rental_resource_calendar_id
        if not calendar_sudo:
            return date

        potential_date = calendar_sudo._get_closest_work_time(
            date, search_range=(date, date + relativedelta(years=3))
        )
        return potential_date or date
