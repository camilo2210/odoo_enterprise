# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_eg_tax(self, taxable_amount):
        # See: https://www.pwc.com/m1/en/services/tax/me-tax-legal-news/2023/egypt-law-no-30-of-2023-issued-by-the-egyptian-government.html
        self.ensure_one()

        def find_rates(x, rates):
            for low, high, bracket_rates in rates:
                if low <= x and (x <= high or self.currency_id.is_zero(high)):
                    return bracket_rates

        rates = self._rule_parameter('l10_eg_tax_rates')
        bracket_rates = find_rates(taxable_amount, rates)
        if not bracket_rates:
            return 0
        total_tax = 0
        for frm, to, rate in bracket_rates:
            if self.currency_id.is_zero(to):  # no upper limit
                total_tax += (taxable_amount - frm) * rate
            else:
                total_tax += min((taxable_amount - frm, to - frm)) * rate
            if taxable_amount <= to:
                break

        return total_tax

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_eg_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_eg_ytd_values(self):
        self.ensure_one()
        last_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', self.struct_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.date_from + relativedelta(month=1, day=1)),
            ('date_to', '<=', self.date_to)
        ])
        line_values = last_payslips._get_line_values(['GROSS', 'TOTTB'], compute_sum=True)
        return {
            'GROSS': line_values['GROSS']['sum']['total'],
            'TOTTB': line_values['TOTTB']['sum']['total'],
        }

    def action_open_eg_tax_adjustment_wizard(self):
        self.ensure_one()
        if self.struct_id.code != 'EGMONTHLY' or self.state != 'draft':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': self.env._('This option only works for draft paysilps with Egypt: Monthly Pay structure.')
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('End of year Tax Adjustment'),
            'res_model': 'l10n.eg.ytd.tax.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _issues_dependencies(self):
        return super()._issues_dependencies() + [
            'employee_id.identification_id',
            'employee_id.passport_id',
            'employee_id.l10n_eg_ssn',
            'employee_id.job_title',
        ]
