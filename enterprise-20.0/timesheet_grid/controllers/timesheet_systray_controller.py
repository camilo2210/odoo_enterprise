from datetime import datetime
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.http import Controller, request, route


class TimesheetSystrayController(Controller):
    @route("/timesheet_grid/timesheet_systray_user_data", type="jsonrpc", auth="user", readonly=True)
    def timesheet_systray_user_data(self, **kwargs):
        employee = request.env.user.employee_id
        if not employee:
            return {"employee": None, "timesheets": []}
        today = fields.Date.context_today(request.env.user)
        return self._get_timesheet_systray_user_data(employee, today, **kwargs)

    def _get_timesheet_systray_user_data(self, employee, date_day, **kwargs):
        timesheet_specification = request.env["account.analytic.line"]._get_aw_timesheet_fields_specification()

        if not employee.sudo()._is_fully_flexible(date_day):
            tz = ZoneInfo(request.env.context.get("tz") or "UTC")
            start_dt = datetime.combine(date_day, datetime.min.time()).replace(tzinfo=tz)
            end_dt = datetime.combine(date_day, datetime.max.time()).replace(tzinfo=tz)
            working_hours = employee._get_work_days_data_batch(start_dt, end_dt)[employee.id]["hours"]
        else:
            working_hours = None

        return {
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "working_hours": working_hours,
            },
            "timesheets": request.env["account.analytic.line"].web_search_read([
                ("user_id", "=", employee.user_id.id),
                ("date", "=", date_day),
                ("project_id", "!=", False),
            ], timesheet_specification),
        }

    @route("/timesheet_grid/get_timer_start_time", type="jsonrpc", auth="user", readonly=True)
    def get_timer_start_time(self):
        employee = request.env.user.employee_id
        if not employee:
            return {"elapsed_seconds": 0}

        today = fields.Date.context_today(request.env.user)
        tz = ZoneInfo(request.env.context.get("tz") or "UTC")
        start_dt = datetime.combine(today, datetime.min.time()).replace(tzinfo=tz)
        end_dt = datetime.combine(today, datetime.max.time()).replace(tzinfo=tz)

        # Check for last timesheet today
        last_timesheet = request.env["account.analytic.line"].search([
            ("employee_id", "=", employee.id),
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
            ("project_id", "!=", False),
        ], order="create_date desc", limit=1)

        if last_timesheet:
            delta = fields.Datetime.now() - last_timesheet.create_date
            return {"elapsed_seconds": delta.total_seconds()}

        # No start time found
        return {"elapsed_seconds": 0}
