# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_is_zero


class HrPayslipEgYtdAdjustmentWizard(models.TransientModel):
    _name = 'l10n.eg.ytd.tax.adjustment.wizard'
    _description = 'Wizard to compute tax adjustment when the employee gets a differnet gross than the expected one due to change in contract'

    payslip_id = fields.Many2one('hr.payslip', required=True, readonly=True, default=lambda self: self.env.context.get('active_id'))
    ytd_gross = fields.Monetary("YTD Gross", compute='_compute_eg_ytd_gross_tax', store=True, readonly=False,
        help="Year-to-date employee's gross income, calculated from current year's validated payslips, including the current payslip.")
    ytd_tax_amount = fields.Monetary("YTD Withheld Tax", compute='_compute_eg_ytd_gross_tax', store=True, readonly=False,
        help="Year-to-date income tax withheld from the employee, calculated from current year's validated payslips, including the current payslip.")
    currency_id = fields.Many2one('res.currency', related='payslip_id.currency_id')
    warning = fields.Char(compute="_compute_warning")

    @api.depends('payslip_id')
    def _compute_eg_ytd_gross_tax(self):
        payslip_lines_ytd = self.payslip_id._get_eg_ytd_values()
        current_payslip_line_values = self.payslip_id._get_line_values(['GROSS', 'TOTTB'])
        self.ytd_gross = payslip_lines_ytd['GROSS'] + current_payslip_line_values['GROSS'][self.payslip_id.id]['total']
        self.ytd_tax_amount = -(payslip_lines_ytd['TOTTB'] + current_payslip_line_values['TOTTB'][self.payslip_id.id]['total'])

    @api.depends('payslip_id')
    def _compute_warning(self):
        month = self.payslip_id.date_from.month
        departure_date = self.payslip_id.employee_id.departure_date
        if month == 12 or (departure_date and month == departure_date.month):
            self.warning = False
        else:
            self.warning = self.env._("This operation is expected to be done in the last payslip of the year")

    def action_confirm_eg_adjustment(self):
        personal_exemption = self.payslip_id._rule_parameter('l10n_eg_lower_boundary')
        taxable_amount = max(0, self.ytd_gross - personal_exemption)
        actual_tax = self.payslip_id._get_eg_tax(taxable_amount)
        tax_difference = self.ytd_tax_amount - actual_tax
        if float_is_zero(tax_difference, precision_digits=2):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': self.env._("The tax value on this payslip is correct and doesn't need adjustment."),
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'soft_reload',
                    },
                }
            }
        if tax_difference < 0:
            self.payslip_id._set_input_value('TAX_CORRECT_NEG', -tax_difference)
            self.payslip_id._set_input_value('TAX_CORRECT_POS', 0)
        else:
            self.payslip_id._set_input_value('TAX_CORRECT_POS', tax_difference)
            self.payslip_id._set_input_value('TAX_CORRECT_NEG', 0)
        self.payslip_id.compute_sheet()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
