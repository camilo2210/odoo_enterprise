from odoo import models
from datetime import datetime, time
from odoo.tools import float_compare
from odoo.tools.date_utils import float_to_time


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    def _handle_flexible_leave_interval(self, dt0, dt1, leave):
        def at_time(d, hour=0, minute=0, second=0, microsecond=0):
            return datetime.combine(
                d.date(),
                time(hour, minute, second, microsecond)
            ).replace(tzinfo=tz)

        tz = dt0.tzinfo
        if leave.sudo().holiday_id.work_entry_type_request_unit == 'half_day':
            dt0 = at_time(dt0) if leave.holiday_id.request_date_from_period == 'am' else at_time(dt0, 12)
            dt1 = at_time(dt1, 12) if leave.holiday_id.request_date_to_period == 'am' else at_time(dt1, 23, 59, 59, 999999)
            return dt0, dt1

        if leave.holiday_id.work_entry_type_request_unit == 'hour':
            if float_compare(leave.holiday_id.number_of_hours, leave.resource_id.hours_per_day, 2) == 0:
                return at_time(dt0), at_time(dt1, 23, 59, 59, 999999)

            if float_compare(leave.holiday_id.number_of_hours, leave.resource_id.hours_per_day / 2, 2) == 0:
                if leave.holiday_id.request_hour_to <= 12.0:
                    return at_time(dt0), at_time(dt1, 12)
                if leave.holiday_id.request_hour_from >= 12.0:
                    return at_time(dt0, 12), at_time(dt1, 23, 59, 59, 999999)

            return (
                datetime.combine(dt0.date(), float_to_time(leave.holiday_id.request_hour_from)).replace(tzinfo=tz),
                datetime.combine(dt1.date(), float_to_time(leave.holiday_id.request_hour_to)).replace(tzinfo=tz),
            )

        return super()._handle_flexible_leave_interval(dt0, dt1, leave)
