# Part of Odoo. See LICENSE file for full copyright and licensing details.
from zoneinfo import ZoneInfo

from odoo import fields, models
from odoo.http import request
from odoo.tools import format_date
from odoo.tools.date_utils import all_timezones


class Website(models.Model):
    _inherit = "website"

    tz = fields.Selection(
        selection="_tz_get",
        required=True,
        default=lambda self: self.env.user.tz or "UTC",
        string="Timezone",
        help="Select your website timezone here.",
    )

    def _tz_get(self):
        return [
            (tz, f"{tz} {self._get_utc_offset(tz)}")
            for tz in sorted(all_timezones, key=lambda tz: tz if not tz.startswith("Etc/") else "_")
        ]

    def _is_customer_in_the_same_timezone(self):
        """Return whether the customer is on the same timezone as the website or not.

        Compare the timezone offset between the website and the customer's browser.

        :return: Whether the customer is on the same timezone as the website or not.
        :rtype: bool
        """
        now = fields.Datetime.now()
        customer_tz = request.cookies.get("tz") if request else None

        return (
            now.replace(tzinfo=ZoneInfo(self.tz)).utcoffset()
            == now.replace(tzinfo=ZoneInfo(customer_tz or "UTC")).utcoffset()
        )

    def _get_utc_offset(self, tz):
        """Return the offset between UTC and the provided timezone.

        :return: (UTC ±HH:MM)
        :rtype: string
        """
        # strftime('%z') return the UTC offset in this form: ±HHMM[SS[.ffffff]]
        utcoffset = fields.Datetime.now().replace(tzinfo=ZoneInfo(tz)).strftime("%z")
        return f"(UTC {utcoffset[0]} {utcoffset[1:3]}:{utcoffset[3:5]})"

    def _format_date(self, datetime):
        """Format a date in the website timezone and the current user's language.

        Since the `format_date` utility function does not take a timezone parameter, we first
        convert the provided datetime to the website timezone before formatting it.
        """
        datetime_in_website_tz = datetime.astimezone(ZoneInfo(self.tz))
        return format_date(self.env, datetime_in_website_tz, lang_code=request.lang.code)
