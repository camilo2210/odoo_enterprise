# Part of Odoo. See LICENSE file for full copyright and licensing details.

import csv
import io
from datetime import datetime, date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'IN' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('advice', 'Payment Advice'),
                ('enet', 'ENet'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'IN' in self.env.companies.country_id.mapped('code'):
            default = 'advice'
        return default

    l10n_in_payment_advice_pdf = fields.Binary('Payment Advice PDF', readonly=True, attachment=False)
    l10n_in_payment_advice_filename_pdf = fields.Char()
    l10n_in_payment_advice_xlsx = fields.Binary('Payment Advice XLSX', readonly=True, attachment=False)
    l10n_in_payment_advice_filename_xlsx = fields.Char()
    l10n_in_enet_csv = fields.Binary('ENet CSV', readonly=True, attachment=False)
    l10n_in_enet_filename_csv = fields.Char(string="ENet Filename CSV")
    l10n_in_reference = fields.Char(string="Report Name")
    l10n_in_valid_bank_accounts_ids = fields.Many2many('res.partner.bank', compute="_compute_bank_account_ids")
    l10n_in_company_bank_id = fields.Many2one('res.partner.bank', string="Company Bank Account",
        domain="[('id', 'in', l10n_in_valid_bank_accounts_ids)]")
    l10n_in_neft = fields.Boolean(string="By NEFT", help="Tick this box if your company use online transfer for salary")
    l10n_in_by_cheque = fields.Boolean(string="By Cheque")
    l10n_in_cheque_number = fields.Char(string="Cheque Number")
    l10n_in_cheque_date = fields.Date(string="Cheque Date")
    l10n_in_state_pdf = fields.Boolean()
    l10n_in_state_xlsx = fields.Boolean()
    l10n_in_state_csv = fields.Boolean()
    l10n_in_payment_method = fields.Selection(
        selection=[
            ('enet_rtgs', 'ENet RTGS'),
            ('enet_neft', 'ENet NEFT'),
            ('enet_fund_transfer', 'ENet Fund Transfer'),
            ('enet_demand_draft', 'ENet Demand Draft'),
            ('enet_intra', 'ENet Intra'),
        ],
        string="Payment Method",
        required=True,
        default='enet_rtgs',
        help="Select Enet to generate the ENet-specific CSV payment file.",
    )

    def _compute_bank_account_ids(self):
        for record in self:
            record.l10n_in_valid_bank_accounts_ids = record.company_id.partner_id.bank_ids

    def _get_report_data(self, payslip):
        employee = payslip.employee_id
        result = []
        allocations = payslip._compute_salary_allocations()

        for bank_account in employee.bank_account_ids | payslip.salary_attachment_ids.beneficiary_bank_account_id:
            amount = allocations.get(str(bank_account.id))
            if not amount:
                continue

            result.append({
                'name': bank_account.holder_name or employee.name,
                'debit_credit': 'C',
                'acc_no': bank_account.account_number or '',
                'ifsc_code': bank_account.bank_bic or '',
                'bysal': amount,
            })
        return result

    def _get_pdf_data(self):
        total_bysal = 0
        lines = []

        for payslip in self.payslip_ids:
            report_line_data = self._get_report_data(payslip)
            lines.extend(report_line_data)
            total_bysal += sum(line['bysal'] for line in report_line_data)

        return {
            'line_ids': {
                'lines': lines,
                'total_bysal': total_bysal,
            },
            'current_date': date.today(),
        }

    def _get_enet_csv_data(self, payslip, index, transaction_type, bank_account, amount, value_date):
        beneficiary_name = bank_account.holder_name or payslip.employee_id.name or ''
        beneficiary_email = bank_account.partner_id.email or payslip.employee_id.private_email or ''
        return [
            transaction_type,  # Transaction Type
            index,  # Beneficiary Code
            bank_account.account_number or '',  # Beneficiary Account Number
            amount,  # Amount
            beneficiary_name,  # Beneficiary Name
            '',  # Drawee Location
            '',  # DD Printing Location
            '',  # Beneficiary Address 1
            '',  # Beneficiary Address 2
            '',  # Beneficiary Address 3
            '',  # Beneficiary Address 4
            '',  # Beneficiary Address 5
            '',  # Instruction Reference Number
            self.l10n_in_reference or '',  # Customer Reference Number
            '',  # Payment Details 1
            '',  # Payment Details 2
            '',  # Payment Details 3
            '',  # Payment Details 4
            '',  # Payment Details 5
            '',  # Payment Details 6
            '',  # Payment Details 7
            '',  # Cheque Number
            value_date,  # Value Date
            '',  # MICR Number
            bank_account.bank_bic or '',  # IFSC Code
            '',  # Beneficiary Bank Name
            '',  # Beneficiary Bank Branch Name
            beneficiary_email,  # Beneficiary Email ID
        ]  # The empty fields are to be filled manually by user, if needed

    def _get_wizard(self, wizard_name):
        return {
            'type': 'ir.actions.act_window',
            'name': wizard_name,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.model_create_multi
    def create(self, vals_list):
        date = datetime.now()
        for vals in vals_list:
            if not vals.get('l10n_in_reference'):
                advice_year = date.strftime('%m-%Y')
                number = self.env['ir.sequence'].next_by_code('payment.advice')
                export_format = vals.get('export_format')
                vals['l10n_in_reference'] = f"PAY/{advice_year}/{number}"\
                    if export_format and export_format != 'enet'\
                    else f"PAYORDER/OUT/{advice_year}/{number}"
        return super().create(vals_list)

    def generate_payment_report_pdf(self):
        self.ensure_one()
        self._perform_checks()

        pdf_content = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
            self.env.ref('l10n_in_hr_payroll.payroll_advice_report').id,
            res_ids=self.ids, data=self._get_pdf_data()
        )[0]

        payment_report = pdf_content
        self.l10n_in_payment_advice_pdf = BinaryBytes(payment_report)
        self.l10n_in_payment_advice_filename_pdf = f"{self.l10n_in_reference}.pdf"
        self._write_file(payment_report, '.pdf', self.l10n_in_reference)
        self.l10n_in_state_pdf = True

        return self._get_wizard(self.env._("Payment Advice"))

    def generate_payment_report_xls(self):
        self.ensure_one()
        self._perform_checks()

        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Payment Advice Report')
        header_format = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'left'})
        cell_format = workbook.add_format({'align': 'left'})
        cell_format_left = workbook.add_format({'bold': True, 'align': 'left'})
        currency_symbol = self.company_id.currency_id.symbol or ''
        currency_format = workbook.add_format({'num_format': f'"{currency_symbol}"#,##0.00', 'align': 'right'})
        total_currency_format = workbook.add_format({'num_format': f'"{currency_symbol}"#,##0.00', 'align': 'right', 'bold': True})
        company_details_header = [
            self.env._('Company Name : ') + self.company_id.name,
            self.env._('Company Bank Account : ') + self.l10n_in_company_bank_id.account_number if self.l10n_in_company_bank_id else '',
        ]
        headers = [
            _('SI No.'),
            _('Name Of Employee'),
            _('C/D'),
            _('Bank Account No.'),
            _('IFSC Code'),
            _('By Salary')
        ]
        worksheet.merge_range(0, 0, 0, len(headers) - 1, company_details_header[0], cell_format_left)
        worksheet.merge_range(1, 0, 1, len(headers) - 1, company_details_header[1], cell_format_left)
        worksheet.write_row(2, 0, headers, header_format)

        total_salary = 0

        row_idx = 3
        for payslip in self.payslip_ids:
            report_rows = self._get_report_data(payslip)
            for row_data in report_rows:
                worksheet.write(row_idx, 0, row_idx - 2, cell_format)
                worksheet.write_row(row_idx, 1, row_data.values(), cell_format)
                if row_data['bysal']:
                    worksheet.write(row_idx, 5, row_data['bysal'], currency_format)
                total_salary += row_data['bysal']
                row_idx += 1

        worksheet.set_column(0, 0, 10)  # SI No.
        worksheet.set_column(1, 1, 20)  # Name Of Employee
        worksheet.set_column(2, 2, 10)  # C/D
        worksheet.set_column(3, 3, 20)  # Bank Account No.
        worksheet.set_column(4, 4, 15)  # IFSC Code
        worksheet.set_column(5, 5, 15)  # By Salary

        row_idx += 1
        worksheet.write(row_idx + 1, 4, "Total:", cell_format_left)
        worksheet.write(row_idx + 1, 5, total_salary, total_currency_format)

        workbook.close()
        xlsx_data = output.getvalue()
        payment_report = xlsx_data

        self.l10n_in_payment_advice_xlsx = BinaryBytes(payment_report)
        self.l10n_in_payment_advice_filename_xlsx = f"{self.l10n_in_reference}.xlsx"
        self._write_file(payment_report, '.xlsx', self.l10n_in_reference)
        self.l10n_in_state_xlsx = True

        return self._get_wizard(self.env._("Payment Report"))

    def generate_enet_csv(self):
        self.ensure_one()
        self._perform_checks()

        csv_data = io.StringIO()
        csv_writer = csv.writer(csv_data, delimiter=',', lineterminator='\r\n')

        headers = [
            ('Transaction Type'),
            ('Beneficiary Code'),
            ('Beneficiary Account Number'),
            ('Amount'),
            ('Beneficiary Name'),
            ('Drawee Location'),
            ('DD Printing Location'),
            ('Beneficiary Address 1'),
            ('Beneficiary Address 2'),
            ('Beneficiary Address 3'),
            ('Beneficiary Address 4'),
            ('Beneficiary Address 5'),
            ('Instruction Reference Number'),
            ('Customer Reference Number'),
            ('Payment Details 1'),
            ('Payment Details 2'),
            ('Payment Details 3'),
            ('Payment Details 4'),
            ('Payment Details 5'),
            ('Payment Details 6'),
            ('Payment Details 7'),
            ('Cheque Number'),
            ('Value Date'),
            ('MICR Number'),
            ('IFSC Code'),
            ('Beneficiary Bank Name'),
            ('Beneficiary Bank Branch Name'),
            ('Beneficiary Email ID'),
        ]

        csv_writer.writerow(headers)

        transaction_type = {
            'enet_rtgs': 'RTGS',
            'enet_neft': 'NEFT',
            'enet_fund_transfer': 'FT',
            'enet_demand_draft': 'DD',
            'enet_intra': 'INTRA',
        }.get(self.l10n_in_payment_method)

        value_date = date.today().strftime('%d/%m/%Y')
        index = 1
        payslips_to_work_on = self.payslip_ids
        if self.include_unpaid:
            payslips_to_work_on = self.unpaid_payslips

        for payslip in payslips_to_work_on:
            allocations = payslip._compute_salary_allocations()
            for bank_account in (
                payslip.employee_id.bank_account_ids
                | payslip.salary_attachment_ids.beneficiary_bank_account_id
            ):
                amount = allocations.get(str(bank_account.id))
                if not amount:
                    continue
                csv_writer.writerow(self._get_enet_csv_data(
                    payslip, index, transaction_type, bank_account, amount, value_date
                ))
                index += 1

        csv_data.seek(0)
        generated_file = csv_data.read()
        csv_data.close()

        enet = generated_file.encode('utf-8')

        self.l10n_in_enet_csv = BinaryBytes(enet)
        self.l10n_in_enet_filename_csv = f"{transaction_type}_{self.l10n_in_reference}.csv"
        self._write_file(enet, '', self.l10n_in_enet_filename_csv)
        self.l10n_in_state_csv = True

        return self._get_wizard(self.env._("ENet CSV"))

    def _perform_checks(self):
        super()._perform_checks()
        if self.company_id.country_code == 'IN':
            payslip_ids = self.payslip_ids.filtered(lambda p: p.state == "validated" and p.net_wage > 0)
            invalid_ifsc_employee_ids = payslip_ids.employee_id._get_employees_with_invalid_ifsc()
            if invalid_ifsc_employee_ids:
                raise UserError(self.env._(
                    'The file cannot be generated, the employees listed below have a bank account with invalid or no bank\'s identification number.\n%s',
                    '\n'.join(invalid_ifsc_employee_ids.mapped('name'))
                ))
