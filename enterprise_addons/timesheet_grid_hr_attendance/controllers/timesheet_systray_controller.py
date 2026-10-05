from odoo import fields
from odoo.http import request, route

from odoo.addons.timesheet_grid.controllers.timesheet_systray_controller import TimesheetSystrayController


class TimesheetSystrayAttendanceController(TimesheetSystrayController):

    @route()
    def get_timer_start_time(self):
        result = super().get_timer_start_time()

        # If no elapsed time from timesheet, check for attendance check-in
        if not result.get("elapsed_seconds"):
            employee = request.env.user.employee_id
            if employee:
                attendance = request.env["hr.attendance"].search([
                    ("employee_id", "=", employee.id),
                    ("check_out", "=", False),  # Currently checked in
                ], order="check_in desc", limit=1)

                if attendance:
                    delta = fields.Datetime.now() - attendance.check_in
                    return {"elapsed_seconds": delta.total_seconds()}

        return result
