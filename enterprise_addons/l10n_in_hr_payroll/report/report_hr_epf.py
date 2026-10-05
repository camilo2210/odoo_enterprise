# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
import io
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes

MONTH_SELECTION = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]


class L10nInHrPayrollEpfReport(models.Model):
    _name = 'l10n.in.hr.payroll.epf.report'
    _description = 'Indian Payroll: Employee Provident Fund Report'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    month = fields.Selection(
        MONTH_SELECTION,
        required=True,
        default=lambda self: str(fields.Date.context_today(self).month)
    )
    export_report_type = fields.Selection(
        [('report', 'EPF Report'), ('summary', 'EPF Summary')],
        default='report', required=True, string="Report Type"
    )
    year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year)
    xls_file = fields.Binary(string="XLS file")

    _unique_epf_report_per_month_year = models.Constraint(
        'UNIQUE(company_id, month, year, export_report_type)',
        "An EPF Report/Summary for this month and year already exists.",
    )

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "IN":
            raise UserError(self.env._('You must be logged in a Indian company to use this feature'))
        return super().default_get(fields)

    @api.depends('month', 'year')
    def _compute_display_name(self):
        month_description = dict(self._fields['month']._description_selection(self.env))
        for report in self:
            report.display_name = f"{month_description.get(report.month)}-{report.year}"

    def _get_employee_epf_data(self):
        self.ensure_one()
        # Get the relevant records based on the year and month
        indian_employees = self.env['hr.employee'].search([
            ('version_id.l10n_in_provident_fund', '=', True),
            ('company_id', '=', self.company_id.id)
        ]).filtered(lambda e: e.company_country_code == 'IN')

        if not indian_employees:
            return []
        result = []

        month = int(self.month)
        end_date = calendar.monthrange(self.year, month)[1]

        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', indian_employees.ids),
            ('date_from', '>=', date(self.year, month, 1)),
            ('date_to', '<=', date(self.year, month, end_date)),
            ('state', 'in', ('validated', 'paid'))
        ])

        if not payslips:
            return []

        if self.export_report_type == 'report':
            payslip_line_values = payslips._get_line_values(['GROSS', 'BASIC', 'PF'])
        else:
            payslip_line_values = payslips._get_line_values(['BASIC', 'PFE', 'PF', 'ERPF'])

        payslips_by_employee = {}
        for slip in payslips:
            payslips_by_employee.setdefault(slip.employee_id, []).append(slip)

        for employee in indian_employees:

            employee_slips = payslips_by_employee.get(employee, [])
            if not employee_slips:
                continue

            wage = 0
            epf = 0
            eps = 0
            pf_value = 0
            total_contribution = 0

            for payslip in employee_slips:
                pf_value -= payslip_line_values['PF'][payslip.id]['total']
                if pf_value == 0:
                    continue

                if self.export_report_type == 'report':
                    wage += payslip_line_values['GROSS'][payslip.id]['total']
                    epf += payslip_line_values['BASIC'][payslip.id]['total']
                else:
                    wage += payslip_line_values['BASIC'][payslip.id]['total']
                    epf -= payslip_line_values['PFE'][payslip.id]['total'] or payslip_line_values['ERPF'][payslip.id]['total']

            # Skip the employee if there are no valid PF contributions
            if not pf_value:
                continue

            # Calculate contributions and differences
            if self.export_report_type == 'report':
                eps = min(employee_slips[0]._rule_parameter('l10n_in_pf_amount'), epf)
            else:
                eps = min(employee_slips[0]._rule_parameter('l10n_in_pf_amount'), wage)
            eps_contri = round(eps * employee_slips[0]._rule_parameter('l10n_in_eps_contri_percent'), 2)

            if self.export_report_type == 'report':
                diff = round(pf_value - eps_contri, 2)
                result.append((
                    str(len(result) + 1),
                    employee.l10n_in_uan or None,
                    employee.legal_name or employee.name,
                    wage,
                    epf,
                    eps,
                    eps,
                    pf_value,
                    eps_contri,
                    diff,
                    0, 0,
                ))
            else:
                admin_charge = round(wage * 0.0050, 2)
                total_contribution = pf_value + epf + eps_contri + admin_charge
                result.append((
                    employee.registration_number or None,
                    employee.legal_name or employee.name,
                    employee.l10n_in_pf_account_number or None,
                    employee.l10n_in_uan or None,
                    wage,
                    pf_value,
                    0,
                    epf,
                    eps_contri,
                    0,
                    admin_charge,
                    total_contribution,
                ))

        return result

    def action_export_xlsx(self):
        self.ensure_one()

        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        if self.export_report_type == 'report':
            self.action_export_epf_report_xlsx(output, workbook)
        else:
            self.action_export_epf_summary_xlsx(output, workbook)

    def action_export_epf_report_xlsx(self, output, workbook):
        self.ensure_one()

        worksheet = workbook.add_worksheet(self.env._('Employee_provident_fund_report'))
        style_main_heading = workbook.add_format({'align': 'center', 'font_size': 20})
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_sub_highlight = workbook.add_format({'bold': True, 'font_size': 11})
        style_normal = workbook.add_format({'font_size': 12})
        headers = [
            'SI NO',
            "UAN",
            "MEMBER NAME",
            "GROSS WAGES",
            "EPF WAGES",
            "EPS WAGES",
            "EDLI WAGES",
            "EPF CONTRIBUTION REMITTED",
            "EPS CONTRIBUTION REMITTED",
            "EPF EPS DIFFERENCE REMITTED",
            "NCP DAYS",
            "REFUNDED OF ADVANCES"
        ]
        month_name = calendar.month_name[int(self.month)]
        worksheet.merge_range(0, 0, 0, len(headers) - 1,
            self.env._('EPF Statement %(month)s-%(year)s', month=month_name, year=self.year),
            style_main_heading,
        )
        employee_epf_rows = self._get_employee_epf_data()
        sub_headers_x_values = {
            self.env._('Name of Establishment'): self.company_id.name,
            self.env._('Establishment ID'): self.company_id.l10n_in_epf_employer_id or '',
            self.env._('Total Members'): str(len(employee_epf_rows)),
        }
        row = 1
        for sub_header, value in sub_headers_x_values.items():
            worksheet.write(row, 0, sub_header, style_sub_highlight)
            worksheet.write(row, 1, value, style_normal)
            row += 1
        worksheet.set_row(row, 20)

        for col, header in enumerate(headers):
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, 30)

        row += 1
        for data_row in employee_epf_rows:
            col = 0
            worksheet.set_row(row, 20)
            for data in data_row:
                worksheet.write(row, col, data, style_normal)
                col += 1
            row += 1

        workbook.close()
        xlsx_data = output.getvalue()

        filename = self.env._("%(display_name)s EPF-ECR Report.xlsx", display_name=self.display_name)
        self.xls_file = BinaryBytes(xlsx_data, filename=filename)

    def action_export_epf_summary_xlsx(self, output, workbook):
        self.ensure_one()

        worksheet = workbook.add_worksheet(self.env._('Employee EPF Summary Report'))
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#B7CCE4', 'align': 'center', 'border': 1})
        style_total = workbook.add_format({'font_name': 'Arial', 'bold': True, 'align': 'center', 'font_size': 12})
        style_note = workbook.add_format({'font_size': 10})
        style_normal = workbook.add_format({'font_size': 12, 'bold': True})
        sub_title_style = workbook.add_format({'font_size': 12, 'bold': True})

        month_name = calendar.month_name[int(self.month)]
        title = self.env._("EPF Summary\nContribution for %(month)s %(year)s", month=month_name, year=self.year)
        worksheet.merge_range(0, 0, 1, 11, title, style_total)

        sub_title = self.env._(
            "%(company_name)s\nEstablishment ID: %(employee_id)s",
            company_name=self.company_id.name,
            employee_id=self.company_id.l10n_in_epf_employer_id or ''
        )
        worksheet.merge_range(2, 0, 3, 11, sub_title, sub_title_style)

        for r in range(4):
            worksheet.set_row(r, 20)

        headers = [
            self.env._("EMPLOYEE ID"),
            self.env._("EMPLOYEE NAME"),
            self.env._("ACCOUNT NUMBER"),
            self.env._("UAN"),
            self.env._("PF WAGES"),
            self.env._("PF AMOUNT"),
            self.env._("VPF AMOUNT"),
            self.env._("PF AMOUNT"),
            self.env._("EPS AMOUNT"),
            self.env._("EDLI"),
            self.env._("PF ADMIN CHARGES"),
            self.env._("TOTAL CONTRIBUTION"),
        ]

        row = 4
        worksheet.set_row(row, 20)

        # write Headers
        for col, header in enumerate(headers):
            if col in [5, 6, 7, 8, 9, 10]:
                if col == 5:
                    # Merge two columns for 'Employee's Contribution'
                    worksheet.merge_range(row, col, row, col + 1, self.env._("Employee's Contribution"), style_highlight)
                elif col == 7:
                    # Merge four columns for 'Employer's Contribution'
                    worksheet.merge_range(row, col, row, col + 3, self.env._("Employer's Contribution"), style_highlight)
                worksheet.write(row + 1, col, header, style_highlight)
            else:
                # Merge single column for other headers
                worksheet.merge_range(row, col, row + 1, col, header, style_highlight)

            worksheet.set_column(col, col, 18)

        rows = self._get_employee_epf_data()

        if rows:
            row = 6
            row_to_sum = row + 1  # Store the row where data starts

            # Employee Data
            for data_row in rows:
                worksheet.set_row(row, 20)
                for col, data in enumerate(data_row):
                    worksheet.write(row, col, data, style_normal)
                row += 1

            # Total Amount Row
            row += 1
            worksheet.merge_range(row, 0, row, 1, self.env._('Total Amount'), style_total)
            worksheet.set_row(row, 20)
            for col in range(4, 12):
                # Sum all rows in the column
                worksheet.write_formula(row, col, f'=SUM({chr(65 + col)}{row_to_sum}:{chr(65 + col)}{row - 1})', style_normal)

            worksheet.merge_range(
                row + 2, 0, row + 2, 4,
                self.env._('Note: According to the EPFO Act, the minimum EPF administrative charges to be paid is Rs. 500.'),
                style_note
            )
        else:
            worksheet.merge_range(
                7, 4, 7, 8,
                self.env._('No Data is Available for the given date'),
                style_total
            )

        workbook.close()
        xlsx_data = output.getvalue()

        filename = self.env._("%(display_name)s EPF-Summary-Report.xlsx", display_name=self.display_name)
        self.xls_file = BinaryBytes(xlsx_data, filename=filename)
