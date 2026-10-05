# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    biometric_event_ids = fields.One2many(
        "hr.attendance.biometric.event",
        "employee_id",
        string="Biometric Events",
        groups="hr_attendance.group_hr_attendance_manager"
    )

    biometric_last_punch_datetime = fields.Datetime(
        string="Last Biometric Punch",
        compute="_compute_biometric_last_punch_datetime",
        store=True,
        groups="hr_attendance.group_hr_attendance_manager",
    )

    @api.depends("biometric_event_ids.punch_datetime", "biometric_event_ids.state")
    def _compute_biometric_last_punch_datetime(self):
        for employee in self:
            processed_events = employee.biometric_event_ids.filtered(
                lambda event: event.state == "processed"
            )
            employee.biometric_last_punch_datetime = max(
                processed_events.mapped("punch_datetime"),
                default=False,
            )
