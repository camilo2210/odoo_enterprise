# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.tools import format_date
from odoo.fields import Domain
from dateutil.relativedelta import relativedelta


class L10n_HkIr56e(models.Model):
    _name = 'l10n_hk.ir56e'
    _inherit = ['l10n_hk.ird']
    _description = 'IR56E Sheet'
    _order = 'submission_date'

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('submission_date')
    def _compute_period(self):
        super()._compute_period()
        """
        While this report is not exactly period-based, we are REQUIRED to report new hires in the first three months
        of their contracts. We can thus reuse the period fields as the valid range for new hires.
        """
        for report in self:
            report.start_period = report.submission_date - relativedelta(months=3)
            report.end_period = report.submission_date

    @api.depends('submission_date')
    def _compute_display_name(self):
        lang_code = self.env.user.lang or 'en_US'
        for sheet in self:
            if sheet.submission_date:
                sheet.display_name = format_date(self.env, sheet.submission_date, date_format="MMMM y", lang_code=lang_code)
            else:
                sheet.display_name = sheet.env._("IR56E Sheet")

    # ----------------
    # Business methods
    # ----------------

    def _get_rendering_data(self, employees):
        self.ensure_one()

        employees_error = self._check_employees(employees)
        if employees_error:
            return {'error': employees_error}

        report_info = self._get_report_info_data()

        # Find the allowance rules that can be set on the employee (input_usage_employee) so that we can sum their value.
        allowance_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'any', [('country_id', '=', self.env.ref('base.hk').id)]),
            ('input_usage_employee', '=', True),
            ('category_ids', 'child_of', self.env.ref('l10n_hk_hr_payroll.ALW').id),
        ])

        employee_declarations = self.line_ids.grouped('employee_id')
        employees_data = []
        for sequence, employee in enumerate(employees.sorted(), start=1):
            # Unlike the other reports, this one need to handle rental differently (we report the contractual amounts, not the actually paid totals)
            rental = employee.l10n_hk_rental_id
            employee_start_date = employee._get_first_version_date()

            per_of_place = ''
            if rental:
                start_str = max(rental.date_start, employee_start_date).strftime('%Y%m%d')
                end_str = rental.date_end.strftime('%Y%m%d') if rental.date_end else ''
                per_of_place = f'{start_str}-{end_str}'

            total_allowance = 0.0
            allowance_rule_codes = set(allowance_rule.filtered(lambda r: employee.structure_id in r.struct_ids).mapped('code'))
            for code in allowance_rule_codes:
                total_allowance += employee.version_id._get_property_input_value(code)

            start_date = employee.contract_date_start
            year_of_return = start_date.year if start_date.month < 4 else start_date.year + 1
            sheet_values = {
                **self._get_employee_data(employee),
                **self._get_employee_spouse_data(employee),
                'SheetNo': sequence,
                'TypeOfForm': employee_declarations.get(employee).l10n_hk_hr_payroll_type_of_form,
                'RTN_ASS_YR': year_of_return,
                'StartDateOfEmp': start_date,
                'monthly_salary': self._format_ird_amount(employee.version_id.wage),
                'monthly_allowance': self._format_ird_amount(employee.version_id.l10n_hk_internet + total_allowance),
                'PlaceOfResInd': int(bool(rental)),
                'AddrOfPlace1': rental and rental.address or '',
                'NatureOfPlace1': rental and rental.nature or '',
                'PerOfPlace1': per_of_place,
                'RentPaidEr1': 0,
                'RentPaidEe1': 0,
                'RentRefund1': 0,
                'RentPaidErByEe1': 0,
                'AmtPaidOverseaCo': employee.version_id._get_property_input_value('OVERSEAS_PAY'),
            }

            if rental:
                match rental.lease_type:
                    case 'reimbursement':
                        sheet_values['RentPaidEe1'] = self._format_ird_amount(rental.amount)
                        sheet_values['RentRefund1'] = self._format_ird_amount(rental.monthly_rent_amount)
                        sheet_values['monthly_salary'] = self._format_ird_amount(employee.version_id.wage - rental.monthly_rent_amount)
                    case 'direct_payment':
                        sheet_values['RentPaidEr1'] = self._format_ird_amount(rental.amount)
                    case 'co_payment':
                        sheet_values['RentPaidEr1'] = self._format_ird_amount(rental.amount)
                        sheet_values['RentPaidErByEe1'] = self._format_ird_amount(rental.co_pay_amount)

            employees_data.append(sheet_values)

        sheets_count = len(employees_data)
        total_data = {
            'NoRecordBatch': f'{sheets_count:05}',
            'TotIncomeBatch': self._format_ird_amount(sum(emp['monthly_salary'] for emp in employees_data)),
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
            ('contract_date_start', '!=', False),
            ('contract_date_start', '>=', self.start_period),
            ('contract_date_start', '<=', self.end_period),
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
                ('version_id.contract_date_start', '>=', self.start_period),
                ('version_id.contract_date_start', '<=', self.end_period),
            ]),
        ])

    def _check_continuity(self, versions_to_report):
        """ For the IR56E, we only pick employees whose real start date (_get_first_version_date) falls in the reported period. """
        non_continuous_versions_ids = set()
        for version_to_report in versions_to_report:
            continuous_start_date = version_to_report.employee_id._get_first_version_date()
            if not (self.start_period <= continuous_start_date <= self.end_period):
                # This handles the "Renewal" case:
                # The employee has a new contract version, but their continuous_start_date
                # is actually 2 years ago. So we SKIP them.
                continue
            non_continuous_versions_ids.add(version_to_report.id)

        return self.env['hr.version'].browse(non_continuous_versions_ids)

    # XML export - for government submission

    def _get_xml_report_xsd_schemas(self, type_of_form):
        self.ensure_one()
        return self._get_xml_resource('ir56e.xsd')

    def _get_xml_report_filename(self, file_number=False):
        """
        Returns the IR56E report filename.
        In case of the report generating multiple files, we will append a file number to the name.
        """
        self.ensure_one()
        company_name = self.company_id.name.replace(' ', '_')
        sub_date = self.submission_date.strftime('%Y%m%d')
        if file_number:
            xml_filename = f'{company_name}_IR56E_{sub_date}_{file_number}.xml'
        else:
            xml_filename = f'{company_name}_IR56E_{sub_date}.xml'
        return xml_filename

    def _get_xml_report_template(self):
        self.ensure_one()
        return 'l10n_hk_hr_payroll.ir56e_xml_report'

    # PDF export - for employee information

    def _get_pdf_report(self):
        return self.env.ref('l10n_hk_hr_payroll.action_report_employee_ir56e')

    def _get_pdf_filename(self, employee):
        self.ensure_one()
        employee_name = employee.name.replace(' ', '_')
        return self.env._('%(employee_name)s_IR56E_%(submission_date)s', employee_name=employee_name, submission_date=self.submission_date)

    def _post_process_rendering_data_pdf(self, rendering_data):
        result = {}
        for sheet_values in rendering_data['employees_data']:
            result[sheet_values['employee']] = {**sheet_values, **rendering_data['data']}
        return result

    def _get_posted_document_owner(self, employee):
        return employee.version_id.hr_responsible_id or self.env.user
