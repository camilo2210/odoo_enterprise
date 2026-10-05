# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import format_date

from .utils import format_amount, format_char


class L10nInTDSChallanLine(models.Model):
    _name = 'l10n.in.tds.challan.line'
    _description = 'Challan Line'
    _order = 'employee_name, paid_date desc'

    challan_id = fields.Many2one('l10n.in.tds.challan', string="Challan", required=True, ondelete='cascade')
    company_id = fields.Many2one(related='challan_id.company_id')
    payslip_id = fields.Many2one('hr.payslip', string="Payslip", required=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', related='payslip_id.employee_id', string="Employee", store=True)
    employee_name = fields.Char(string="Employee Name", related='employee_id.name')
    pan = fields.Char(string="PAN", related='employee_id.l10n_in_pan', store=True)
    paid_date = fields.Date(string="Paid Date", related='payslip_id.date_to', store=True, readonly=False)
    currency_id = fields.Many2one(related='company_id.currency_id')
    net_wage = fields.Monetary(string="Net Wage", related='payslip_id.net_wage')
    total_tds_paid = fields.Monetary(string="Total TDS", required=True)

    def _prepare_dd_record(self, line_number, challan_sequence, deductee_sequence):
        """Prepare the Form 138 Deductee Detail (DD) record containing an employee's
        payment and the tax deducted and deposited under the challan.

        Format reference: https://tinpan.proteantech.in/downloads/e-tds/eTDS-download-regular.html
        """
        self.ensure_one()
        total_tds = self.total_tds_paid
        payment_date = self.paid_date
        pan = self.pan or 'PANNOTAVBL'
        return [
            str(line_number),  # Line Number
            'DD',  # Record Type
            '1',  # Batch Number
            str(challan_sequence),  # Challan-Detail Record Number
            str(deductee_sequence),  # Deductee / Detail Record No
            'O',  # Mode
            '',  # Last deductee PAN (not applicable)
            pan,  # Deductee's PAN
            format_char(self.employee_id.name, 75),  # Name of Employee
            '',  # Remarks 1 (for future use)
            '',  # Remarks 2 (for future use)
            '',  # Remarks 3 (for future use)
            '',  # Remarks 4 (for future use)
            '',  # Remarks 5 (for future use)
            self.challan_id.form_138_id._get_salary_section_code(),  # Section Code under which payment made
            '',  # Remarks 6 (for future use)
            '',  # Remarks 7 (for future use)
            'Y',  # Whether the total amount of tax deducted has been deposited
            format_date(self.env, payment_date, date_format='ddMMY'),  # Date of payment / Credited
            format_amount(self.net_wage),  # Amount Paid/ Credited
            '',  # Grossing up Indicator (not applicable)
            '',  # Remarks 9 (for future use)
            '',  # Remarks 10 (for future use)
            format_amount(total_tds),  # Total Tax Deducted
            format_amount(total_tds),  # Total Tax Deposited
            '',  # Last total Tax deducted (Used for Verification) (Not Applicable)
            format_date(self.env, payment_date, date_format='ddMMY') if total_tds else '',  # Date of deduction
            '',  # Remarks 11 (for future use)
            format_date(self.env, self.challan_id.paid_date, date_format='ddMMY') if total_tds else '',  # Date of deposit
            '',  # Remarks 12 (for future use)
            '',  # Remarks 13 (for future use)
            'C' if not self.pan else '',  # Reason for non-deduction/lower deduction/higher deduction
            '',  # Certificate number(s) of the certificate under section 395(1)
            '',  # Filler 1
            '',  # Filler 2
            '',  # Filler 3
            '',  # Filler 4
            '',  # Filler 5
            '',  # Filler 6
            '',  # Filler 7
            '',  # Filler 8
            '',  # Last Total Tax Deposited (Used for Verification) (Not applicable)
            '',  # Filler 10
            '',  # Filler 11
            '',  # Record Hash (not applicable)
        ]
