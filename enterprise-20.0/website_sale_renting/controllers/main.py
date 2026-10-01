# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields
from odoo.http import request, route
from odoo.tools.date_utils import localized, to_timezone

from odoo.addons.sale_renting.controllers.utils import _convert_rental_dates
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleRenting(WebsiteSale):
    def _get_search_options(self, **post):
        options = super()._get_search_options(**post)
        options.update({
            "from_date": post.get("start_date"),
            "to_date": post.get("end_date"),
            "rent_only": post.get("rent_only") in ("True", "true", "1"),
        })
        return options

    def _shop_get_query_url_kwargs(self, search, min_price, max_price, **kwargs):
        result = super()._shop_get_query_url_kwargs(search, min_price, max_price, **kwargs)
        result.update(start_date=kwargs.get("start_date"), end_date=kwargs.get("end_date"))
        return result

    @route()
    def shop(self, *args, **kwargs):
        _convert_rental_dates(kwargs)
        if (
            self
            .env["ir.config_parameter"]
            .sudo()
            # Allow disabling rental price computation for more than one periodicity if performance
            # is an issue.
            .get_bool("website_sale_renting.shop_compute_rental_price", True)
            and (start_date := kwargs.get("start_date"))
            and (end_date := kwargs.get("end_date"))
        ):
            # if provided, forward dates to `_get_combination_info` call
            request.update_context(start_date=start_date, end_date=end_date)
        return super().shop(*args, **kwargs)

    @route()
    def product(self, *args, **kwargs):
        _convert_rental_dates(kwargs)
        if (start_date := kwargs.get("start_date")) and (end_date := kwargs.get("end_date")):
            # if provided, forward dates to `_get_combination_info` call
            request.update_context(start_date=start_date, end_date=end_date)
        return super().product(*args, **kwargs)

    @route(
        "/rental/product/constraints",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
        readonly=True,
    )
    def renting_product_constraints(self, min_date, max_date):
        """Return rental product constraints.

        Constraints are the working days and hours when rentals can be picked up and returned,
        as well as the minimal duration of the rental period, if the current cart imposes one.

        :param string min_date: The start date for the interval, in UTC
        :param string max_date: The end date for the interval, in UTC
        :rtype: dict
        :return: The renting constraints in the website's timezone in the following format:
            {
                'has_rental_calendar': bool,
                'working_days_and_hours': dict(str, list(dict(str, int))),
                'minimum_rental_duration': float | None,
            }
        """
        working_days_and_hours = defaultdict(list)
        calendar_sudo = self.env.company.sudo().rental_resource_calendar_id
        min_dt = fields.Datetime.to_datetime(min_date)
        max_dt = fields.Datetime.to_datetime(max_date)
        if calendar_sudo and min_dt and max_dt:
            to_website_tz = to_timezone(ZoneInfo(self.env.website.tz))
            tz_min_date = to_website_tz(localized(min_dt))
            tz_max_date = to_website_tz(localized(max_dt))
            tz_now = to_website_tz(localized(fields.Datetime.now()))
            # Received intervals in the website's timezone
            intervals_dict = calendar_sudo._work_intervals_batch(tz_min_date, tz_max_date)
            intervals = intervals_dict.get(False, [])
            # Working days and hours {'2026-03-01': [{"hour": 9, "minute": 0}, ...], ...}
            for i, (start, end, _) in enumerate(intervals):
                if i == 0 and start.date() == tz_now.date():
                    # Round the first interval, starting "now", up to the nearest hour
                    start = (start + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                iso_date = start.date().isoformat()
                working_days_and_hours[iso_date].extend(self._get_time_options(start, end))
        result = {
            "has_rental_calendar": bool(calendar_sudo),
            "working_days_and_hours": working_days_and_hours,
        }
        if order_sudo := request.cart:
            minimum_duration = order_sudo._get_minimum_rental_duration()
            if minimum_duration is not None:
                result["minimum_rental_duration"] = minimum_duration.total_seconds()
        return result

    @route(
        "/rental/product/availabilities",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def renting_product_availabilities(self, _product_id, _min_date, _max_date):
        """Return rental product availabilities.

        Availabilities are the available quantities of a product for a given period. This is
        expressed by a dict {'start': ..., 'end': ..., 'available_quantity': ...).

        :rtype: dict
        """
        return {}

    @api.model
    def _get_time_options(self, start: datetime, end: datetime):
        """Create a list of {"hour": int, "minute": int} dicts with a 1-hour interval.

        :param datetime start: The start of the interval.
        :param datetime end: The end of the interval.
        :return: list of hour/minute dicts
        :rtype: list[dict[str, int]]
        """
        options = []
        current_dt = start
        while current_dt <= end:
            options.append({"hour": current_dt.hour, "minute": current_dt.minute})
            current_dt += timedelta(hours=1)
        return options

    def _get_additional_shop_values(self, values, start_date=None, end_date=None, **kwargs):
        try:
            start_date = fields.Datetime.to_datetime(start_date)
            end_date = fields.Datetime.to_datetime(end_date)
        except ValueError:
            start_date = end_date = None
        vals = super()._get_additional_shop_values(
            values, start_date=start_date, end_date=end_date, **kwargs
        )
        vals.update({"start_date": start_date, "end_date": end_date})
        return vals

    def _get_product_query_params(self, start_date=None, end_date=None, **kwargs):
        res = super()._get_product_query_params(start_date=start_date, end_date=end_date, **kwargs)
        if start_date is not None or end_date is not None:
            res.update({"start_date": start_date, "end_date": end_date})
        return res
