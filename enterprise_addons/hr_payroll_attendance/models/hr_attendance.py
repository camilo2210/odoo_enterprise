# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    category_options_ids = fields.Many2many(
        'hr.salary.rule.category',
        string='Payroll Options',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('optional_on_work_entry_type_ids', 'in', work_entry_type_id)]",
    )

    payslip_id = fields.Many2one(
        'hr.payslip',
        string="Payslip",
        compute="_compute_payslip_id",
        groups="hr_payroll.group_hr_payroll_user",
    )

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_payslip_id(self):
        for attendance in self:
            if not (attendance.employee_id and attendance.check_in and attendance.check_out):
                attendance.payslip_id = False
                continue

            attendance.payslip_id = self.env['hr.payslip'].search(
                attendance._get_payslip_domain(),
                limit=1,
                order='date_from desc, id desc',
            )

    def _get_payslip_domain(self):
        self.ensure_one()
        localized_check_in, _localized_check_out = self._get_localized_times()
        return [
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '<=', localized_check_in.date()),
            ('date_to', '>=', localized_check_in.date()),
            ('state', 'not in', ['draft', 'cancel']),
        ]

    def action_open_payslip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.payslip_id.display_name,
            'res_model': 'hr.payslip',
            'res_id': self.payslip_id.id,
            'view_mode': 'form',
        }
