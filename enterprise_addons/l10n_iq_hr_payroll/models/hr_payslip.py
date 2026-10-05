# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_sspc_contribution_base(self):
        self.ensure_one()
        first_payslip_of_the_year = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', self.date_from.replace(month=1, day=1)),
            ('date_to', '<=', self.date_to.replace(month=12, day=31)),
        ], order='date_from asc', limit=1)
        res = 0
        if first_payslip_of_the_year == self:
            return res
        for line in first_payslip_of_the_year.line_ids.filtered(lambda line: 'FW' in line.category_ids.mapped('code')):
            if line.code == 'BASIC':
                res += first_payslip_of_the_year.version_id.wage
                continue
            res += line.amount
        return res

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_iq_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]
