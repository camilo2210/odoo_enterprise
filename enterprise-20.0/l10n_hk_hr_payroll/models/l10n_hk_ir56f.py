# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import date

from odoo import api, fields, models
from odoo.fields import Domain
from dateutil.relativedelta import relativedelta


class L10n_HkIr56f(models.Model):
    _name = 'l10n_hk.ir56f'
    _inherit = ['l10n_hk.ird']
    _description = 'IR56F Sheet'
    _order = 'start_period'

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('start_year', 'start_month', 'end_year', 'end_month')
    def _compute_period(self):
        super()._compute_period()
        for record in self:
            record.end_period = date(record.start_year + 1, int(record.end_month), 31)

    # ----------------
    # Business methods
    # ----------------

    @api.model
    def _check_employees(self, employees):
        error_messages = super()._check_employees(employees)
        invalid_lines = self.line_ids.filtered(lambda line: not line.employee_id.departure_reason_id.l10n_hk_ir56f_code)
        if invalid_lines:
            error_messages += "\n" + self.env._(
                "The following employees don't have a valid departure reason: %s",
                invalid_lines.employee_id.mapped("name"),
            )
        invalid_lines = self.line_ids.filtered(lambda line: not line.employee_id.departure_date or line.employee_id.l10n_hk_leaving_hk)
        if invalid_lines:
            error_messages += "\n" + self.env._(
                "The following employees' contract does not have a departure date, or they were marked as leaving Hong Kong: %s",
                invalid_lines.employee_id.mapped("name"),
            )
        invalid_lines = self.line_ids.filtered(
            lambda line: line.employee_id.departure_reason_id.l10n_hk_ir56f_code == '5' and not line.employee_id.departure_description
        )
        if invalid_lines:
            error_messages += "\n" + self.env._(
                "The following employees don't have a reason set for their departure of type 'Other': %s",
                invalid_lines.employee_id.mapped("name"),
            )
        return error_messages

    def _get_rendering_data(self, employees):
        self.ensure_one()

        employees_error = self._check_employees(employees)
        if employees_error:
            return {'error': employees_error}

        report_info = self._get_report_info_data()

        payslip_info = self._get_employees_payslip_data(employees)
        if 'error' in payslip_info:
            return {'error': payslip_info['error']}
        all_payslips = payslip_info['all_payslips']

        employee_payslips = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in all_payslips.sorted('employee_id'):
            employee_payslips[payslip.employee_id] |= payslip

        all_lines_values = all_payslips._get_line_values(set(all_payslips.line_ids.mapped('code')), compute_sum=True)

        employee_declarations = self.line_ids.grouped('employee_id')
        employees_data = []
        for sequence, employee in enumerate(employee_payslips, start=1):
            sheet_line = self.line_ids.filtered(lambda line: line.employee_id == employee)
            payslips = employee_payslips[employee]

            mapped_total = {
                code: sum(all_lines_values[code][p.id]['total'] for p in payslips)
                for code in all_lines_values
            }

            start_date = self.start_period if self.start_period > employee._get_first_version_date() else employee._get_first_version_date()
            end_date = employee.version_id.departure_date if employee.version_id.departure_date else self.end_period
            _, categories_totals = payslips._l10n_hk_aggregate_totals(all_lines_values)

            departure_code = sheet_line.employee_id.departure_reason_id.l10n_hk_ir56f_code
            if departure_code == '5':
                departure_reason_other = fields.Html.to_plaintext(sheet_line.employee_id.departure_description)
                departure_reason_str = fields.Html.to_plaintext(sheet_line.employee_id.departure_description)
            elif departure_code:
                departure_reason_other = ''
                departure_reason_str = {
                    '1': 'Resignation',
                    '2': 'Retirement',
                    '3': 'Dismissal',
                    '4': 'Death',
                }[departure_code]

            year_of_return = end_date.year if end_date.month < 4 else end_date.year + 1
            employees_data.append({
                **self._get_employee_data(employee),
                **self._get_employee_spouse_data(employee),
                **self._get_employee_rental_data(employee, payslips, all_lines_values),
                **self._get_employee_rap_data(payslips, all_lines_values),
                'date_from': self.start_period,
                'date_to': self.end_period,
                'SheetNo': sequence,
                'TypeOfForm': employee_declarations.get(employee).l10n_hk_hr_payroll_type_of_form,
                'CESSATION_DATE': end_date,
                'CESSATION_REASON': departure_code,
                'CESSATION_REASON_OTHER': departure_reason_other,
                'cessation_reason_str': departure_reason_str,
                'RTN_ASS_YR': year_of_return,
                'StartDateOfEmp': start_date,
                'EndDateOfEmp': end_date,
                'AmtOfSalary': self._format_ird_amount(categories_totals['HK_BASIC']),
                'AmtOfLeavePay': self._format_ird_amount(categories_totals['LEAVE_PAY']),
                'AmtOfDirectorFee': self._format_ird_amount(categories_totals['DIRECTOR_FEE']),
                'AmtOfBpEtc': self._format_ird_amount(categories_totals['BACKPAY'] + categories_totals['PILON']),
                'AmtOfPayRetire': self._format_ird_amount(categories_totals['RETIREMENT']),
                'AmtPaidOverseaCo': self._format_ird_amount(categories_totals['OVERSEAS_INCOME']),
                'AmtOfCommFee': self._format_ird_amount(categories_totals['COMMISSION']),
                'AmtOfBonus': self._format_ird_amount(categories_totals['BONUS']),
                'AmtOfSalTaxPaid': self._format_ird_amount(categories_totals['TAX_PAID']),
                'AmtOfEduBen': self._format_ird_amount(categories_totals['EDUCATION']),
                'AmtOfGainShareOption': self._format_ird_amount(categories_totals['SHARE_OPTION']),
                'TotalIncome': self._format_ird_amount(categories_totals['GROSS'] - mapped_total.get('HRA', 0)),
                'AmtOfEEMC': self._format_ird_amount(mapped_total.get('EEMC', 0)),
                'AmtOfERMC': self._format_ird_amount(mapped_total.get('ERMC', 0)),
                'AmtOfEEVC': self._format_ird_amount(mapped_total.get('EEVC', 0)),
                'AmtOfERVC': self._format_ird_amount(mapped_total.get('ERVC', 0)),
            })

        sheets_count = len(employees_data)

        total_data = {
            'NoRecordBatch': '{:05}'.format(sheets_count),
            'TotIncomeBatch': self._format_ird_amount(sum(ed['TotalIncome'] for ed in employees_data)),
        }

        return {'data': report_info, 'employees_data': employees_data, 'total_data': total_data}

    def _get_report_version_domain(self):
        """
        Domain used to filter the employees that should appear in the report.
        This should pick all employees eligible for declarations in the report; a separate check will be done to remove
        those that were already declared in the same period.
        """
        self.ensure_one()
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('departure_date', '!=', False),
            ('departure_date', '>=', self.start_period),
            ('departure_date', '<=', self.end_period),
            ('l10n_hk_leaving_hk', '=', False),
        ])

    def _get_report_sheet_domain(self):
        """
        We'll find all reports who are declaring versions matching the _get_report_version_domain, this way we
        are sure to catch duplicated.
        """
        self.ensure_one()
        return Domain([
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id),
            ('line_ids', 'any', [
                ('version_id.departure_date', '!=', False),
                ('version_id.departure_date', '>=', self.start_period),
                ('version_id.departure_date', '<=', self.end_period),
                ('version_id.l10n_hk_leaving_hk', '=', False),
            ]),
        ])

    def _check_continuity(self, versions_to_report):
        """ For the IR56F, we only pick employees who do not have another version starting soon after. """
        non_continuous_versions_ids = set()
        if not versions_to_report:
            return versions_to_report

        min_cessation_date = min(versions_to_report.mapped("departure_date"))
        future_data = self.env["hr.version"]._read_group(
            domain=[
                ("employee_id", "in", versions_to_report.employee_id.ids),
                ("contract_date_start", ">", min_cessation_date),
                ("company_id", "=", self.company_id.id),
            ],
            groupby=["employee_id"],
            aggregates=[
                "contract_date_start:min"
            ],  # We only care about the immediate successor
        )
        next_start_map = {
            employee.id: next_start for employee, next_start in future_data
        }

        for version_to_report in versions_to_report:
            next_start = next_start_map.get(version_to_report.employee_id.id)
            if next_start and next_start <= (version_to_report.departure_date + relativedelta(days=4)):
                continue
            non_continuous_versions_ids.add(version_to_report.id)

        return self.env['hr.version'].browse(non_continuous_versions_ids)

    # XML export - for government submission

    def _get_xml_report_xsd_schemas(self, type_of_form):
        self.ensure_one()
        return self._get_xml_resource('ir56f.xsd')

    def _get_xml_report_filename(self, file_number=False):
        """
        Returns the IR56F report filename.
        In case of the report generating multiple files, we will append a file number to the name.
        """
        self.ensure_one()
        company_name = self.company_id.name.replace(' ', '_')
        sub_date = self.submission_date.strftime('%Y%m%d')
        if file_number:
            xml_filename = f'{company_name}_IR56F_{sub_date}_{file_number}.xml'
        else:
            xml_filename = f'{company_name}_IR56F_{sub_date}.xml'
        return xml_filename

    def _get_xml_report_template(self):
        self.ensure_one()
        return 'l10n_hk_hr_payroll.ir56f_xml_report'

    # PDF export - for employee information

    def _get_pdf_report(self):
        return self.env.ref('l10n_hk_hr_payroll.action_report_employee_ir56f')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        employee_name = employee.name.replace(' ', '_')
        return self.env._('%(employee_name)s_IR56F_%(start_year)s', employee_name=employee_name, start_year=self.start_year)

    def _post_process_rendering_data_pdf(self, rendering_data):
        result = {}
        for sheet_values in rendering_data['employees_data']:
            result[sheet_values['employee']] = {**sheet_values, **rendering_data['data']}
        return result

    def _get_posted_document_owner(self, employee):
        return employee.version_id.hr_responsible_id or self.env.user
