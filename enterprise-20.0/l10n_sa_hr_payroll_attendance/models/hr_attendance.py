# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    l10n_sa_expected_check_in = fields.Datetime(string="Expected Check In", compute="_compute_l10n_sa_expected_check_in",
        help="The expected check-in time based on the employee's calendar.")
    l10n_sa_late_hours = fields.Float(string='Late Hour', compute='_compute_late_hour', store=True, tracking=True,
        help="The number of hours the employee is late for the check-in time.")
    l10n_sa_late_hours_status = fields.Selection(
        selection=[
            ('to_approve', 'Draft'),
            ('approved', 'Confirm'),
        ],
        string='Late Hours Status', compute='_compute_l10n_sa_late_hours_status', store=True, tracking=True, readonly=False)
    l10n_sa_late_hours_visible = fields.Boolean(
        string='Late Hours Visible',
        compute='_compute_l10n_sa_late_hours_visible',
        store=True,
        help="Indicates whether the late hours are visible to the employee or not.")

    @api.depends('employee_id', 'check_in', 'employee_id.company_id.country_id')
    def _compute_l10n_sa_late_hours_visible(self):
        """
            Compute the visibility of late hours for attendance records.

            Late hours should be visible only on the first attendance record per day per employee.
            This means late hours are shown only on the record corresponding to the employee's first check-in for that day.
            Subsequent check-ins or check-outs on the same day for the same employee will not display late hours.
        """
        sa_attendances = self.filtered(lambda att: att.employee_id.company_id.country_id.code == 'SA')
        non_sa_attendances = self - sa_attendances
        non_sa_attendances.l10n_sa_late_hours_visible = False

        if not sa_attendances:
            return

        sa_attendances_with_check_in = sa_attendances.filtered('check_in')
        if not sa_attendances_with_check_in:
            sa_attendances.l10n_sa_late_hours_visible = False
            return

        date_min = min(sa_attendances_with_check_in.mapped('check_in')).date()
        date_max = max(sa_attendances_with_check_in.mapped('check_in')).date()
        attendance_by_employee = self.env['hr.attendance']._read_group(domain=[
            ('employee_id', 'in', sa_attendances.employee_id.ids),
            ('check_in', '>=', date_min),
            ('check_in', '<=', date_max),
        ], groupby=['employee_id', 'check_in:day'], aggregates=['id:recordset'])
        attendance_to_be_updated = self.env['hr.attendance']
        for _employee, _day, attendances in attendance_by_employee:
            attendance_to_be_updated |= min(attendances, key=lambda x: x.check_in)
        for attendance in sa_attendances:
            attendance.l10n_sa_late_hours_visible = attendance in attendance_to_be_updated

    @api.depends('employee_id', 'check_in')
    def _compute_l10n_sa_expected_check_in(self):
        for attendance in self:
            if attendance.employee_id and attendance.check_in and (calendar := attendance.employee_id.resource_calendar_id):
                # Get the expected check-in time based on the employee's calendar
                expected_time = calendar._l10n_sa_get_expected_check_in(attendance.check_in, attendance.employee_id.resource_id)
                attendance.l10n_sa_expected_check_in = expected_time
            else:
                attendance.l10n_sa_expected_check_in = False

    @api.depends('check_in', 'l10n_sa_expected_check_in')
    def _compute_late_hour(self):
        for attendance in self:
            employee_grace = attendance.employee_id.company_id.l10n_sa_late_employee_grace / 60.0
            if attendance.check_in and attendance.l10n_sa_expected_check_in:
                late_duration = attendance.check_in - attendance.l10n_sa_expected_check_in
                attendance.l10n_sa_late_hours = max(0, late_duration.total_seconds() / 3600.0 - employee_grace)
            else:
                attendance.l10n_sa_late_hours = 0.0

    @api.depends('l10n_sa_late_hours', 'l10n_sa_late_hours_visible')
    def _compute_l10n_sa_late_hours_status(self):
        for attendance in self:
            if attendance.l10n_sa_late_hours > 0 and attendance.l10n_sa_late_hours_visible:
                attendance.l10n_sa_late_hours_status = 'to_approve'
            else:
                attendance.l10n_sa_late_hours_status = 'approved'

    def _update_l10n_sa_late_hours(self):
        latetime_vals_list = []
        latetime_to_remove = self.env['l10n.sa.hr.attendance.latetime'].search([
            ('attendance_id', 'in', self.ids),
        ])
        # Remove existing work entries for late hours
        latetime_to_remove.unlink()
        for attendance in self.filtered(lambda att: att.l10n_sa_late_hours_visible):
            late_duration = attendance.l10n_sa_late_hours
            if float_compare(late_duration, 0, precision_digits=2) == 1 and attendance.l10n_sa_late_hours_status == 'approved':
                # Create a work entry for the late hours
                latetime_vals_list.append({
                    'employee_id': attendance.employee_id.id,
                    'attendance_id': attendance.id,
                    'date_from': attendance.check_in - timedelta(hours=late_duration),
                    'date_to': attendance.check_in,
                    'duration': late_duration,
                })
        self.env['l10n.sa.hr.attendance.latetime'].create(latetime_vals_list)

    def write(self, vals):
        if any(field in vals for field in ['employee_id', 'check_in']):
            self.filtered(lambda attendance: attendance.employee_id.sudo().country_code == 'SA')._update_l10n_sa_late_hours()
        return super().write(vals)

    def action_approve_l10n_sa_late_hours(self):
        to_approve_attendances = self.filtered(lambda att: att.l10n_sa_late_hours_status == 'to_approve')
        if not to_approve_attendances:
            raise UserError(self.env._("Late hours can only be approved from the draft state."))
        to_approve_attendances.l10n_sa_late_hours_status = 'approved'
        to_approve_attendances._update_l10n_sa_late_hours()
        return True

    def action_refuse_l10n_sa_late_hours(self):
        to_refuse_attendances = self.filtered(lambda att: att.l10n_sa_late_hours_status == 'approved')
        if not to_refuse_attendances:
            raise UserError(self.env._("Late hours can only be refused from the confirmed state."))
        to_refuse_attendances.l10n_sa_late_hours_status = 'to_approve'
        to_refuse_attendances._update_l10n_sa_late_hours()
        return True
