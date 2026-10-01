from datetime import date, datetime
from zoneinfo import ZoneInfo

from odoo import api, models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def lazy_session_info(self):
        res = super().lazy_session_info()

        if not self.env.user.has_group("hr_timesheet.group_hr_timesheet_user"):
            return res | {
                "display_timesheets_systray": False,
            }

        employee = self.env.user.employee_id
        if not employee:
            employee_data = None
        else:
            if employee.resource_calendar_id or (employee.hours_per_week and employee.hours_per_day):
                tz = ZoneInfo(self.env.context.get("tz") or "UTC")
                start_dt = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=tz)
                end_dt = datetime.combine(date.today(), datetime.max.time()).replace(tzinfo=tz)
                working_hours = employee._get_work_days_data_batch(start_dt, end_dt)[employee.id]["hours"]
            else:
                working_hours = None
            employee_data = {
                "id": employee.id,
                "name": employee.name,
                "working_hours": working_hours,
            }

        timesheet_specification = self.env["account.analytic.line"]._get_aw_timesheet_fields_specification()
        if not employee:
            timesheets_today = []
        else:
            timesheets_today = self.env["account.analytic.line"].web_search_read([
                ("user_id", "=", employee.user_id.id),
                ("date", "=", date.today()),
                ("project_id", '!=', False),
            ], timesheet_specification)

        fake_new_timesheet = self.env['account.analytic.line'].new()
        default_values = fake_new_timesheet.read(list(timesheet_specification.keys()))[0]
        default_values.pop('id', None)

        uom_hour = self.env.ref("uom.product_uom_hour", raise_if_not_found=False)
        res |= {
            "display_timesheets_assistant": self.env.user.has_group("timesheet_grid.group_timesheet_assistant"),
            "display_timesheets_systray": self.env.company.timesheet_encode_uom_id == uom_hour
                and self.env.user.has_group("hr_timesheet.group_hr_timesheet_user")
                and bool(self.env.user.employee_ids),
            "timesheet_systray_employee_data": employee_data,
            "timesheet_rounding_values": self.env["account.analytic.line"]._get_rounding_values(),
            "timesheet_default_values": default_values,
            "timesheets_today": timesheets_today,
            "timesheet_timer_fields": self.env['account.analytic.line'].fields_get(list(timesheet_specification.keys())),
        }
        return res
