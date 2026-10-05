# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_pk_get_tax(self, income):
        self.ensure_one()
        result = 0
        tax_brackets = list(iter(self._rule_parameter('l10n_pk_tax_brackets')))
        for i, (low, high, rate, fix) in enumerate(tax_brackets):
            if income > low:
                if income <= high:
                    result += rate * (income - low)
                    break
                else:
                    result = fix
        return result

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_pk_hr_payroll', [
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]

    def _get_pk_ytd_values(self):
        self.ensure_one()
        last_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('struct_id', '=', self.struct_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.date_from + relativedelta(month=1, day=1)),
            ('date_to', '<=', self.date_to)
        ])
        line_values = last_payslips._get_line_values(['GROSS', 'TXW'], compute_sum=True)
        return {
            'GROSS': line_values['GROSS']['sum']['total'],
            'TXW': line_values['TXW']['sum']['total'],
        }

    def action_open_pk_tax_adjustment_wizard(self):
        self.ensure_one()
        if self.struct_id.code != 'PKMONTHLY' or self.state != 'draft':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': self.env._('This option only works for draft paysilps with Pakistan: Regular Pay structure.')
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('End of year Tax Adjustment'),
            'res_model': 'l10n.pk.ytd.tax.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
