# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _l10n_sa_late_hours(self):
        l10n_sa_late_hours_by_employee = dict(self.env['l10n.sa.hr.attendance.latetime']._read_group(
            domain=[('employee_id', 'in', self.employee_id.ids), ('deducted', '=', False)],
            groupby=['employee_id'],
            aggregates=['id:recordset']))

        balance_by_employee = {}
        for payslip in self:
            if not payslip.employee_id or not payslip.date_from or not payslip.date_to or payslip.country_code != 'SA':
                continue
            if payslip.struct_id.code == 'SALARYADVANDLOAN':
                continue
            l10n_sa_late_hours = l10n_sa_late_hours_by_employee.get(payslip.employee_id, self.env['l10n.sa.hr.attendance.latetime']).filtered(
                lambda x: x.date_from.date() >= payslip.date_from and x.date_to.date() <= payslip.date_to)
            balance = sum(late.duration for late in l10n_sa_late_hours)
            if balance <= 0:
                continue
            balance_by_employee[payslip.employee_id] = balance
        return balance_by_employee

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to')
    def _compute_input_line_ids(self):
        res = super()._compute_input_line_ids()
        latehours_balance = self._l10n_sa_late_hours()
        for slip in self:
            if not slip.employee_id or not slip.date_from or not slip.date_to or slip.country_code != 'SA':
                continue
            if slip.struct_id.code == 'SALARYADVANDLOAN':
                continue
            latehours = latehours_balance.get(slip.employee_id, 0)
            slip._set_input_value('LATE_HOURS', latehours)
        return res

    def write(self, vals):
        res = super().write(vals)
        l10n_sa_late_hours_by_employee = dict(self.env['l10n.sa.hr.attendance.latetime']._read_group(
            domain=[('employee_id', 'in', self.employee_id.ids)],
            groupby=['employee_id'],
            aggregates=['id:recordset']))
        if 'state' in vals and vals['state'] == 'paid':
            # When the payslip is paid, we mark the late hours as deducted
            for slip in self.filtered(lambda r: 'LATE_DEDUCTION' in r.line_ids.mapped('code')):
                l10n_sa_late_hours = l10n_sa_late_hours_by_employee.get(slip.employee_id, self.env['l10n.sa.hr.attendance.latetime']).filtered(
                    lambda x: x.date_from.date() >= slip.date_from and x.date_to.date() <= slip.date_to)
                l10n_sa_late_hours.write({'deducted': True})
        return res
