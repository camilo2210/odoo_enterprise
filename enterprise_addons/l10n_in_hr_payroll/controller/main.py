# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from io import BytesIO
from copy import deepcopy

from odoo import fields, http, _
from odoo.http import request

from dateutil.relativedelta import relativedelta


class L10nInSalaryRegisterController(http.Controller):

    def _get_payslip_rules(self, employee_ids, payslips, struct_id=None):
        rule_by_name = []
        if struct_id and struct_id.rule_ids:
            rule_by_name = [(i.code, i.name) for i in struct_id.rule_ids]
        else:
            rule_by_name = [
                (rule.code, rule.name)
                for payslip in payslips
                for rule in payslip.struct_id.rule_ids
            ]
        child_dict = {code: [name, 0] for code, name in rule_by_name}
        rules_per_employee = {employee_id: deepcopy(child_dict) for employee_id in employee_ids}
        rules_by_name = dict(rule_by_name)
        return rules_by_name, rules_per_employee

    @http.route(['/export/salary-register/<int:wizard_id>'], type='http', auth='user')
    def export_salary_register(self, wizard_id):
        wizard = request.env['salary.register.wizard'].browse(wizard_id)
        if not wizard.exists() or not request.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            return request.render(
                'http_routing.http_error',
                {
                    'status_code': 'Oops',
                    'status_message': _('It seems that you either not have the rights to access the Salary Register '
                                        'or that you try to access it outside normal circumstances. '
                                        'If you think there is a problem, please contact an administrator.')
                }
            )
        output = BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('salary_register_report')
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'left'})
        style_normal = workbook.add_format({'align': 'left'})
        style_horizontal_data = workbook.add_format({'align': 'right'})
        column_width = 30

        date_from = str(wizard.date_from)
        date_to = str(wizard.date_to)
        employee_ids = wizard.employee_ids
        struct_id = wizard.struct_id

        #  VERTICAL HEADERS
        vertical_headers = [
            _('EMPLOYER ID'),
            _('EMPLOYER NAME'),
            _('FROM DATE'),
            _('TO DATE'),
        ]
        # VERTICAL DATA
        vertical_data = [
            wizard.company_id.l10n_in_corporate_identification_number or '',
            wizard.company_id.name,
            date_from,
            date_to,
        ]
        blank_lines = 1

        # HORIZONTAL HEADERS
        horizontal_headers = [
            _('EMPLOYEE CODE'),
            _('EMPLOYEE NAME'),
        ]

        # HORIZONTAL DATA
        domain = wizard._get_payslip_domain()
        domain.append(('employee_id', 'in', employee_ids.ids))
        if struct_id:
            domain.append(('struct_id', '=', struct_id.id))
        payslips_per_employee = dict(request.env['hr.payslip']._read_group(
                domain=domain,
                groupby=['employee_id'],
                aggregates=['id:recordset'],
            ))
        rules_by_name, rules_per_employee = self._get_payslip_rules(employee_ids, payslips_per_employee.values(), struct_id=struct_id)
        rules_per_employee = {
            employee: rules
            for employee, rules in rules_per_employee.items()
            if employee in payslips_per_employee
        }
        # Dynamically calculated headers
        horizontal_headers = [*horizontal_headers, *rules_by_name.values()]
        for employee_id, payslips in payslips_per_employee.items():
            rule_codes = payslips.struct_id.rule_ids.mapped('code')
            payslip_rules = payslips._get_line_values(rule_codes, compute_sum=True)
            for code, rule in payslip_rules.items():
                rules_per_employee[employee_id][code][1] += rule['sum']['total']

        horizontal_data = []
        for employee_id in rules_per_employee:
            dynamic_horizontal_data = [data[1] for data in rules_per_employee[employee_id].values()]
            horizontal_data.append((
                employee_id.registration_number or "",
                employee_id.name,
                *dynamic_horizontal_data,
            ))

        # WRITE IN WORKSHEET
        row = 0
        for (vertical_header, vertical_point) in zip(vertical_headers, vertical_data):
            worksheet.write(row, 0, vertical_header, style_highlight)
            worksheet.write(row, 1, vertical_point, style_normal)
            row += 1

        row += blank_lines
        for col, horizontal_header in enumerate(horizontal_headers):
            worksheet.write(row, col, horizontal_header, style_highlight)
            worksheet.set_column(col, col, column_width)

        for payroll_line in horizontal_data:
            row += 1
            for col, payroll_point in enumerate(payroll_line):
                worksheet.write(row, col, payroll_point, style_normal)
                if isinstance(payroll_point, (int, float)):
                    worksheet.write(row, col, payroll_point, style_horizontal_data)

        row += 1
        workbook.close()
        xlsx_data = output.getvalue()
        date_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        filename = _("salary_register_report_%(year)s_%(month)s", year=date_obj.year, month=date_obj.month)
        response = request.make_response(
            xlsx_data,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}.xlsx')],
        )
        return response


class L10nInHrPayrollLabourWelfareFundController(http.Controller):
    @http.route("/export/labour_welfare_fund/<int:wizard_id>", type='http', auth='user')
    def export_labour_welfare_fund(self, wizard_id):
        wizard = request.env['l10n.in.labour.welfare.fund.wizard'].browse(wizard_id)
        if not wizard.exists() or not request.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            return request.render(
                'http_routing.http_error', {
                    'status_code': 'Oops',
                    'status_message': "Please contact an administrator..."})

        output = BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Worksheet')
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'left'})
        style_normal = workbook.add_format({'align': 'center'})
        style_horizontal_data = workbook.add_format({'align': 'left'})
        style_header_info = workbook.add_format({'align': 'left', 'text_wrap': True})
        style_title = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 32})
        currency_symbol = wizard.currency_id.symbol or ''
        style_currency_symbol = workbook.add_format({'num_format': f'"{currency_symbol}" #,##0.00', 'align': 'right'})

        worksheet.merge_range('A1:F1', 'Labour Welfare Fund Summary', style_title)
        labour_id = wizard.company_id.l10n_in_labour_identification_number or ""
        worksheet.merge_range('A2:F2', f'{wizard.company_id.name}\nLabour Identification Number: {labour_id}', style_header_info)
        worksheet.set_row(1, 30)
        worksheet.merge_range('A3:F3', f'{wizard.date_from.strftime("%d/%m/%Y")} to {wizard.date_to.strftime("%d/%m/%Y")}', style_normal)

        headers = [
            _("LWF Account Number"),
            _("Employee ID"),
            _("Employee Name"),
            _("Employees' Contribution"),
            _("Employer's Contribution"),
            _("Total Contribution"),
        ]

        row = 3
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, len(header) + 2)

        data = []
        for line in wizard.line_ids:
            data.append([
                line.employee_lwf_account or "",
                line.employee_id.registration_number or "",
                line.employee_name,
                line.employee_contibution,
                line.employer_contribution,
                line.total_contribution,
            ])
        row += 1
        for record in data:
            col = 0
            for info in record:
                worksheet.write(row, col, info, style_currency_symbol)
                if isinstance(info, str):
                    worksheet.write(row, col, info, style_horizontal_data)
                col += 1
            row += 1

        workbook.close()
        xlsx_data = output.getvalue()
        response = request.make_response(
            xlsx_data,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename=labour_welfare_fund.xlsx')],
        )
        return response


class L10nInGratuityCalculationReportController(http.Controller):
    @http.route("/export/gratuity_calculation_report/<int:wizard_id>", type='http', auth='user')
    def export_gratuity_calculation(self, wizard_id):
        wizard = request.env['l10n.in.gratuity.calculation.report.wizard'].browse(wizard_id)
        if not wizard.exists() or not request.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            return request.render(
                'http_routing.http_error', {
                    'status_code': 'Oops',
                    'status_message': self.env._('Please contact an administrator...')})

        employee_data = self._generate_rows(wizard)

        headers = [
            self.env._("Sr. No"),
            self.env._("Employee"),
            self.env._("Date of Joining"),
            self.env._("Last Working Day"),
            self.env._("Basic+DA"),
            self.env._("Number of Year"),
            self.env._("Number of month"),
            self.env._("No. of Year for Calculation"),
            self.env._("Gratuity Amount"),
            self.env._("Gratuity Eligibility"),
        ]

        return self._generate_xlsx(employee_data, headers)

    def _generate_rows(self, wizard):
        today = fields.Date.context_today(self)
        selection_mode = wizard.selection_mode
        employee_ids = wizard.employee_ids
        struct_id = wizard.struct_id

        domain = [('state', 'in', ['validated', 'paid']), ('employee_id', 'in', employee_ids.ids)]
        if selection_mode == "salary_structure":
            domain.append(('struct_id', '=', struct_id))

        payslips = request.env['hr.payslip'].search(domain, order='date_from desc')
        latest_payslips = {}
        for payslip in payslips:
            emp_id = payslip.employee_id.id
            if emp_id not in latest_payslips:
                latest_payslips[emp_id] = payslip

        employee_data = []
        for sr_no, employee in enumerate(employee_ids, start=1):
            first_contract_date = employee._get_first_version_date()
            last_working_day = today if not employee.version_id.date_end else employee.version_id.date_end
            difference = relativedelta(last_working_day, first_contract_date)
            year_calculation = (difference.years + 1) if difference.months > 6 else difference.years
            basicDA = latest_payslips[employee.id]._get_line_values(['BASIC'])['BASIC'][latest_payslips[employee.id].id]['total']
            gratuity = round(basicDA * year_calculation * (15 / 26), 2)
            date_end = "-" if not employee.version_id.date_end else employee.version_id.date_end.strftime('%d/%m/%Y')

            employee_data.append([
                sr_no,
                employee.name,
                first_contract_date.strftime('%d/%m/%Y'),
                date_end,
                basicDA,
                difference.years,
                difference.months,
                year_calculation,
                gratuity,
                "Eligible" if year_calculation >= 5 else "Not Eligible"
            ])

        employee_data.append(wizard.company_id.currency_id.symbol or '')

        return employee_data

    def _generate_xlsx(self, employee_data, headers):
        output = BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Gratuity Calculation Report')
        style_highlight = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0', 'align': 'center'})
        style_normal = workbook.add_format({'align': 'center'})
        style_normal_left = workbook.add_format({'align': 'left'})
        style_currency_symbol = workbook.add_format({'num_format': f'"{employee_data[-1]}" #,##0.00', 'align': 'right'})
        style_title = workbook.add_format({'bold': True, 'align': 'center', 'font_size': 20})
        worksheet.merge_range('A1:J1', 'Gratuity Calculation Report', style_title)
        column_width = 30

        row = 1
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, style_highlight)
            worksheet.set_column(col, col, column_width)

        for data in employee_data[:-1]:
            row += 1
            for col, value in enumerate(data):
                if col == 0 or col == 1:
                    style = style_normal_left
                elif col == 4 or col == 8:
                    style = style_currency_symbol
                else:
                    style = style_normal
                worksheet.write(row, col, value, style)

        note = self.env._('Note: Gratuity is calculated using the following formula: (Last Drawn Salary × 15 / 26) × Years of Service')
        worksheet.merge_range(row + 3, 0, row + 3, 2, note, style_normal_left)
        workbook.close()
        xlsx_data = output.getvalue()
        response = request.make_response(
            xlsx_data,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename=gratuity_calculation_report.xlsx')],
            )
        return response
