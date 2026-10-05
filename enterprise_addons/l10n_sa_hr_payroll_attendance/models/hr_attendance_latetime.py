# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nSAHrAttendanceLatetime(models.Model):
    _name = "l10n.sa.hr.attendance.latetime"
    _description = "Attendance Latetime"

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", default=lambda self: self.env.user.employee_id,
        required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='employee_id.company_id')

    attendance_id = fields.Many2one('hr.attendance', string="Attendance", ondelete='cascade')
    date_from = fields.Datetime(string='Expected Checkin', required=True)
    date_to = fields.Datetime(string='Actual Checkin', required=True)
    duration = fields.Float(string='Extra Hours', default=0.0, required=True)
    deducted = fields.Boolean(string='Deducted', default=False, help="Indicates whether the late hours have been deducted or not.")
