from datetime import UTC
from zoneinfo import ZoneInfo

from odoo import models


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _l10n_sa_get_expected_check_in(self, check_in, resource=None):
        """
        Get the expected check-in time based on the employee's calendar.
        This method should be overridden in the specific calendar implementation.
        """
        self.ensure_one()
        if resource and not resource._is_fully_flexible() and resource._is_flexible():
            return check_in
        tz = resource.tz if resource else self.tz
        check_in = check_in.astimezone(ZoneInfo(tz))  # Ensure check_in has timezone info
        closest_work_time = self._get_closest_work_time(check_in, resource=resource)
        closest_work_time = closest_work_time.astimezone(UTC) if closest_work_time else check_in.astimezone(UTC)
        return closest_work_time.replace(tzinfo=None)
