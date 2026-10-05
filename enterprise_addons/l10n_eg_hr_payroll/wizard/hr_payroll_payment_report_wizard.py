# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from odoo import models


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def _get_export_format_selection(self):
        selection = super()._get_export_format_selection()
        if 'EG' in self.env.companies.country_id.mapped('code'):
            selection.extend([
                ('l10n_eg_eta_form2', 'ETA Form2'),
            ])
        return selection

    def _get_default_export_format(self):
        default = super()._get_default_export_format()
        if 'EG' in self.env.companies.country_id.mapped('code'):
            default = 'l10n_eg_eta_form2'
        return default

    def _generate_l10n_eg_eta_form2_file(self):
        import xlsxwriter  # noqa: PLC0415

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_normal = workbook.add_format({'align': 'center'})
        headers = [
            self.env._('Serial Number'),
            self.env._('Employee Name'),
            self.env._('National Number/ID'),
            self.env._('Passport Number'),
            self.env._('Insurance State'),
            self.env._('Insurance Number'),
            self.env._('Job Position'),
            self.env._('Total Amount Paid to Employee'),
        ]
        row = 0
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 30)

        def get_eta_form2_row(payslip, sequence):
            employee = payslip.employee_id
            return [
                sequence, employee.name, employee.identification_id, employee.passport_id or '',
                1 if employee.l10n_eg_ssn else 0, employee.l10n_eg_ssn or '', employee.job_title or '',
                payslip.net_wage,
            ]

        for row, payslip in enumerate(self.payslip_ids, start=1):
            for col, data in enumerate(get_eta_form2_row(payslip, row)):
                worksheet.write(row, col, data, style_normal)

        workbook.close()
        xls_file_name = self.env._(
            'ETA Form 2 Report - Payment on %(date)s %(month)s',
            date=self.effective_date.strftime('%d'),
            month=self.effective_date.strftime('%B')
        )
        return output.getvalue(), xls_file_name

    def generate_payment_report(self):
        super().generate_payment_report()
        if self.export_format == 'l10n_eg_eta_form2':
            eta_report, eta_report_name = self._generate_l10n_eg_eta_form2_file()
            self._write_file(eta_report, '.xlsx', eta_report_name)
