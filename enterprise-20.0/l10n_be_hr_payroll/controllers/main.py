# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
import logging
import re

from dateutil.relativedelta import relativedelta

from odoo import fields, http
from odoo.http import request
from odoo.http.stream import content_disposition

from odoo.addons.hr_payroll.controllers.main import HrPayroll

_logger = logging.getLogger(__name__)


class L10nBeHrPayrollEcoVoucherController(http.Controller):

    @http.route(["/export/ecovouchers/<int:wizard_id>"], type='http', auth='user')
    def export_eco_vouchers(self, wizard_id):
        wizard = request.env['l10n.be.eco.vouchers.wizard'].browse(wizard_id)
        if not wizard.exists() or not request.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            return request.render(
                'http_routing.http_error', {
                    'status_code': 'Oops',
                    'status_message': "Please contact an administrator..."})

        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Worksheet')
        style_highlight = workbook.add_format({
            'bold': True,
            'pattern': 1,
            'bg_color': '#E0E0E0',
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        style_normal = workbook.add_format({'align': 'center'})
        row = 0
        reference_year = wizard.reference_year

        headers = [
            self.env._("National registration number (e.g. 790227 183 12)"),
            self.env._("Employee last name (e.g. jansen)"),
            self.env._("Employee first name (e.g. max)"),
            self.env._("Your internal employee number (e.g. 152d97)"),
            self.env._("Number voucher [a] (e.g. 18)"),
            self.env._("Value voucher [b] (e.g. 5.5)"),
            self.env._("Total [a] x [b] (e.g. 99)"),
            self.env._("Employee birth date (dd/mm/yyyy)"),
            self.env._("Employee gender (m/f)"),
            self.env._("Employee language (nl/fr/en)"),
            self.env._("Cost center (e.g. cc1. maximum 10 characters)"),
            self.env._("Your company number  (e.g. be 0834013324)"),
            self.env._("Delivery address street (e.g. av. des volontaires)"),
            self.env._("Delivery address number (e.g. 19)"),
            self.env._("Delivery address box  (e.g. b2)"),
            self.env._("Delivery address zipcode (e.g. 1160)"),
            self.env._("Delivery address city (e.g. oudergem)"),
            self.env._("Contract status"),
        ]

        rows = []
        for line in wizard.line_ids:
            employee = line.employee_id
            employee_name = re.sub(r"[\(].*?[\)]", "", employee.legal_name)
            quantity = 1
            amount = round(line.amount, 2)
            birthdate = employee.birthday or fields.Date.today()
            lang = employee.lang
            if lang == 'fr_FR':
                lang = 'FR'
            elif lang == 'nl_NL':
                lang = 'NL'
            else:
                lang = 'EN'

            rows.append((
                employee.niss.replace('.', '').replace('-', '') if employee.niss else '',
                employee_name.split(' ')[0],
                ' '.join(employee_name.split(' ')[1:]),
                ' ',
                quantity,
                amount,
                quantity * amount,
                f'{birthdate:%m/%d/%Y}',
                'F' if employee.sex == 'female' else 'M',
                lang,
                ' ', ' ', ' ', ' ', ' ', ' ', ' ',
                self.env._('Active') if employee.version_id.is_current else self.env._('End of collaboration'),
            ))

        col = 0
        for header in headers:
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 15)
            col += 1

        row = 1
        for employee_row in rows:
            col = 0
            for employee_data in employee_row:
                worksheet.write(row, col, employee_data, style_normal)
                col += 1
            row += 1

        workbook.close()
        xlsx_data = output.getvalue()
        response = request.make_response(
            xlsx_data,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename=Eco_vouchers_{reference_year}.xlsx')],
        )
        return response


class L10nBeHrPayroll(HrPayroll):

    @http.route()
    def get_payroll_report_print(self, list_ids='', **post):
        res = super().get_payroll_report_print(list_ids, **post)
        ids = [int(s) for s in list_ids.split(',') if s.isdigit()]

        if len(ids) == 1:
            payslip = request.env['hr.payslip'].browse(ids)
            if payslip.struct_id.code == 'BEHOLN':
                res.headers.set(
                    'Content-Disposition',
                    content_disposition(f"Holiday {payslip.employee_id.legal_name} - Certificate {payslip.date_from.strftime('%Y')}.pdf"))
            elif payslip.struct_id.code == 'BEHOLN1':
                res.headers.set(
                    'Content-Disposition',
                    content_disposition(f"{payslip.employee_id.legal_name} - Holiday Certificate {(payslip.date_from - relativedelta(years=1)).strftime('%Y') }.pdf"))

        return res
