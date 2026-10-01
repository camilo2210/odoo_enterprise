# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
from odoo.fields import Domain


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    @api.model
    def _get_start_payrun_warnings(self, versions, date_start, date_end):
        warnings = super()._get_start_payrun_warnings(versions, date_start, date_end)
        attendance_versions = versions.filtered('attendance_based')
        if not attendance_versions:
            return warnings
        pending_overtime_domain = Domain.AND([
            Domain('employee_id', 'in', attendance_versions.employee_id.ids),
            Domain('check_out', '>=', date_start),
            Domain('check_in', '<=', date_end),
            Domain('overtime_status', '=', 'to_approve'),
        ])
        if self.env['hr.attendance'].search_count(pending_overtime_domain, limit=1):
            warnings.append({
                'title': self.env._("Attendances to Review"),
                'body': self.env._("Attendances must be approved before validating final payslips."),
                'reviewLabel': self.env._("Record Time"),
                'reviewAction': {
                    'name': self.env._('Pay Run Employee Records'),
                    'type': 'ir.actions.act_window',
                    'views': [(False, 'gantt'), (False, 'list'), (False, 'kanban')],
                    'res_model': 'hr.attendance',
                    'domain': pending_overtime_domain,
                },
            })
        employees_with_attendance = self.env["hr.attendance"]._read_group(
            domain=Domain.AND([
                Domain('employee_id', 'in', attendance_versions.employee_id.ids),
                Domain('check_out', '>=', date_start),
                Domain('check_in', '<=', date_end),
            ]),
            groupby=['employee_id'],
        )
        employees_with_attendance_ids = {employee.id for employee, in employees_with_attendance}
        if set(attendance_versions.employee_id.ids) - employees_with_attendance_ids:
            warnings.append({
                'title': self.env._("No Attendance"),
                'body': self.env._("There is no attendance for some employee, is it normal?"),
                'reviewLabel': self.env._("Record Time"),
                'reviewAction': {
                    'name': self.env._('Pay Run Employee Records'),
                    'type': 'ir.actions.act_window',
                    'views': [(False, 'gantt'), (False, 'list'), (False, 'kanban')],
                    'res_model': 'hr.attendance',
                    'domain': Domain('employee_id', 'in', attendance_versions.employee_id.ids),
                },
            })
        return warnings
