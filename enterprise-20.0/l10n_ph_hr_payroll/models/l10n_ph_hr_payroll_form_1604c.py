# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

import calendar
from odoo import api, fields, models
from io import BytesIO
from odoo.tools import plaintext2html
from collections import defaultdict, Counter


class L10nPhHrPayrollForm1604C(models.Model):
    _name = 'l10n_ph_hr_payroll.form_1604c'
    _inherit = 'l10n_ph_hr_payroll.declaration'
    _description = 'Form 1604-C'

    period_start_date = fields.Date(
        default=lambda s: fields.Date.today() + relativedelta(day=1, month=1, years=-1),
    )
    period_end_date = fields.Date(
        default=lambda s: fields.Date.today() + relativedelta(day=31, month=12, years=-1),
    )
    warning_text = fields.Text(
        readonly=True,
    )
    period_1601c_declaration_ids = fields.One2many(
        comodel_name='l10n_ph_hr_payroll.form_1601c',
        inverse_name='period_1604c_declaration_id',
        string='1601-C Declarations',
        compute='_compute_period_1601c_declaration_ids',
        store=True,
    )
    period_2316_declaration_ids = fields.One2many(
        comodel_name='l10n_ph_hr_payroll.form_2316',
        inverse_name='period_1604c_declaration_id',
        string='2316 Declarations',
        compute='_compute_period_2316_declaration_ids',
        store=True,
    )

    @api.depends('period_end_date')
    def _compute_name(self):
        for sheet in self:
            declaration_name = sheet._get_declaration_name()
            if sheet.period_end_date:
                sheet.name = f"{declaration_name} - {sheet.period_end_date.year}"
            else:
                sheet.name = declaration_name

    @api.depends('period_start_date', 'period_end_date', 'state')
    def _compute_period_1601c_declaration_ids(self):
        for declaration in self:
            declaration.period_1601c_declaration_ids = self.env['l10n_ph_hr_payroll.form_1601c'].search([
                ('company_id', '=', declaration.company_id.id),
                ('period_start_date', '>=', declaration.period_start_date),
                ('period_end_date', '<=', declaration.period_end_date),
                ('state', '=', 'done'),
            ])

    @api.depends('period_start_date', 'period_end_date', 'state')
    def _compute_period_2316_declaration_ids(self):
        for declaration in self:
            declaration.period_2316_declaration_ids = self.env['l10n_ph_hr_payroll.form_2316'].search([
                ('company_id', '=', declaration.company_id.id),
                ('period_start_date', '>=', declaration.period_start_date),
                ('period_end_date', '<=', declaration.period_end_date),
                ('state', '=', 'done'),
            ])

    def _get_declaration_name(self):
        self.ensure_one()
        return self.env._("Form 1604-C")

    def action_confirm_declaration(self):
        self._assert_employee_declarations()
        super().action_confirm_declaration()

    def action_generate_declarations(self):
        super().action_generate_declarations()
        self._assert_employee_declarations()

    def _assert_employee_declarations(self):
        """
        The assertion here doesn't validate the employee's data as this has been done for the other reports.
        But we need to make sure that:
            - All employees are parts of each month's 1601-C if they had a payslip in that month.
            - All employees are parts of the yearly 2316 if they had a payslip in that year.
        We'll display a warning in case of errors, as the 1604-C is expected to match the list of 2316, and the summary
        is a recap of the 1601-C.
        """
        self.ensure_one()
        warnings = []
        # Start by getting all payslips in the period for the populated employees.
        structures = self._get_relevant_structures()
        all_payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('date_to', '>=', self.period_start_date),
            ('date_to', '<=', self.period_end_date),
            ('employee_id', 'in', self.line_ids.employee_id.ids),
            ('struct_id', 'in', structures.ids),
            ('company_id', '=', self.company_id.id),
        ])
        # Check 1: 1601-C
        missing_months = {p.date_to.month for p in all_payslips} - {d.period_end_date.month for d in self.period_1601c_declaration_ids}
        if missing_months:
            month_names = [calendar.month_name[m] for m in sorted(missing_months)]
            warnings.append(self.env._("Missing or unposted 1601-C for: %(months)s", months=', '.join(month_names)))

        declarations_by_period = self.period_1601c_declaration_ids.grouped(lambda decl: (decl.period_start_date, decl.period_end_date))
        for (date_from, date_to), declaration in declarations_by_period.items():
            decl_employees = declaration.line_ids.employee_id
            payslip_employees = all_payslips.filtered(lambda p: date_from <= p.date_to <= date_to).employee_id
            missing_employees = payslip_employees - decl_employees
            if missing_employees:
                warnings.append(self.env._("The following employees are missing from the %(month)s 1601-C: %(employees)s", month=calendar.month_name[date_to.month], employees=', '.join(missing_employees.mapped('name'))))
        # Check 2: 2316
        decl_employees = self.period_2316_declaration_ids.line_ids.employee_id
        payslip_employees = all_payslips.employee_id
        missing_employees = payslip_employees - decl_employees
        if missing_employees:
            warnings.append(self.env._("The following employees are missing from the Form 2316: %(employees)s", employees=', '.join(missing_employees.mapped('name'))))

        self.warning_text = '\n'.join(warnings)

    def action_generate_files(self):
        """
        The 1604-C declaration comprises two steps.
        - A manual filling the eBIR Forms.
        - A data upload with details.

        In order to facilitate both, we will generate two different file formats.
        For the first step, we will generate a summary XLSX that is basically a list of all 1601-C for the year;
        and in the second step we will generate the DAT files following the official structure in order to allow for
        an easy upload to the government portal.
        """
        self.ensure_one()
        summary_file = self._generate_summary_file()
        alphalist_file = self._generate_alphalist_file()
        # Store a copy of the attachment in the chatter.
        if self.warning_text:
            message = self.env._('Files generated with warnings:\n%(warnings)s', warnings=self.warning_text)
        else:
            message = self.env._('Files successfully generated.')
        self.message_post(
            body=plaintext2html(message),
            attachment_ids=(summary_file | alphalist_file).ids,
        )
        return summary_file | alphalist_file

    def _generate_summary_file(self):
        """
        Prepare the summary XLSX file for the 1604-C declaration.
        Currently only supports the summary of the 1601-C declarations of the whole year.
        """
        self.ensure_one()

        output = BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(self.env._('Annual Information Return of Income Taxes Withheld on Compensation and Final Withholding Taxes'))

        worksheet.merge_range(
            0, 0,
            0, 6,
            'Remittance per BIR Form No. 1601-C',
            cell_format=workbook.add_format({'bold': True, 'align': 'center'})
        )
        worksheet.write_row(1, 0, [
            'MONTH',
            'DATE OF REMITTANCE',
            'NAME OF BANK/BANK CODE/ROR NO., IF ANY',
            'TAXES WITHHELD',
            'ADJUSTMENT',
            'PENALTIES',
            'TOTAL AMOUNT REMITTED',
        ])

        decl_per_month = self.period_1601c_declaration_ids.grouped(lambda decl: decl.period_end_date.month)
        totals = [0, 0, 0, 0]
        for i in range(1, 13):
            period_1601c_declaration = decl_per_month.get(i)
            if period_1601c_declaration:
                # If a given month has multiple returns (e.g. filling an amended return to correct something) we pick the latest one.
                latest_1601c = period_1601c_declaration.sorted('create_date desc')[0]

                worksheet.write_row(i + 1, 0, (
                    calendar.month_abbr[i].upper(),
                    latest_1601c.remittance_date and latest_1601c.remittance_date.strftime("%d-%b-%Y") or '',
                    '',
                    self._format_value(latest_1601c.total_tax_withheld, preserve_sign=True, stringify=False),
                    self._format_value(latest_1601c.total_tax_adjustment, preserve_sign=True, stringify=False),
                    self._format_value(latest_1601c.penalties, preserve_sign=True, stringify=False),
                    self._format_value(latest_1601c.total_still_due, preserve_sign=True, stringify=False),
                ))
                totals[0] += latest_1601c.total_tax_withheld
                totals[1] += latest_1601c.total_tax_adjustment
                totals[2] += latest_1601c.penalties
                totals[3] += latest_1601c.total_still_due
            else:
                worksheet.write_row(i + 1, 0, (
                    calendar.month_abbr[i].upper(),
                    '',
                    '',
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ))

        worksheet.write_row(14, 0, (
            '',
            '',
            '',
            self._format_value(totals[0], preserve_sign=True, stringify=False),
            self._format_value(totals[1], preserve_sign=True, stringify=False),
            self._format_value(totals[2], preserve_sign=True, stringify=False),
            self._format_value(totals[3], preserve_sign=True, stringify=False),
        ))
        workbook.close()
        attachment = self.env['ir.attachment'].create({
            'name': f"1604C_Summary_{self.period_end_date.year}_{self.company_id.name}.xlsx",
            'raw': output.getvalue(),
            'res_model': self._name,
            'res_id': self.id,
        })
        return attachment

    def _generate_alphalist_file(self):
        """
        Note: We try to write the branch code in four digit if possible. Nowadays, the BIR give 5 digits branch code to
        companies, but the alphalist system doesn't support it at all.
        As it's unlikely to have more than 9999 branches, the current logic should be enough.
        """
        self.ensure_one()
        Form2316 = self.env['l10n_ph_hr_payroll.form_2316']

        structures = self._get_relevant_structures()
        all_payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.period_start_date),
            ('date_to', '<=', self.period_end_date),
            ('employee_id', 'in', self.line_ids.employee_id.ids),
            ('struct_id', 'in', structures.ids),
            ('company_id', '=', self.company_id.id),
        ]).grouped('employee_id')

        company_tin = self.company_id.vat and self.company_id.vat.replace('-', '').replace(' ', '')[:9] or ''
        company_branch_code = (self.company_id.l10n_ph_branch_code or '').lstrip('0').zfill(4)[:4]
        dat_data_lines = [','.join([
            'H1604C',                                                                                                   # Form Type Code
            company_tin,                                                                                                # Employer's TIN
            company_branch_code,                                                                                        # Employer's Branch Code
            self.period_end_date.strftime("%m/%d/%Y")                                                                   # Return Period
        ])]
        mwe_employees = self.line_ids.employee_id.filtered('l10n_ph_hr_payroll_minimum_wage_earner').sorted('l10n_ph_legal_last_name')
        regular_employees = (self.line_ids.employee_id - mwe_employees).sorted('l10n_ph_legal_last_name')

        schedules = [
            ('D1', regular_employees),
            ('D2', mwe_employees)
        ]
        for schedule, employees in schedules:
            if not employees:
                continue

            schedule_totals = Counter()
            for i, employee in enumerate(employees, start=1):
                employee_payslips = all_payslips.get(employee, self.env['hr.payslip'])
                all_lines_values = employee_payslips._get_line_values(set(employee_payslips.line_ids.mapped('code')), vals_list=['total', 'ytd'], compute_sum=True)
                dec_tax_total = all_lines_values['WITHH_TAX'][employee_payslips.sorted('date_to desc')[0].id]
                rule_totals, categories_totals = employee_payslips._l10n_ph_hr_payroll_aggregate_totals(all_lines_values)
                employee_rendering_data = {}

                Form2316._add_employee_data(employee_rendering_data, employee)
                Form2316._add_current_employer_data(employee_rendering_data, employee)
                Form2316._add_previous_employer_data(employee_rendering_data, employee, period_end_date=self.period_end_date)
                employee_totals = defaultdict(float)
                Form2316._calculate_non_tax_compensation(employee_totals, employee, rule_totals, categories_totals, period_end_date=self.period_end_date)
                Form2316._calculate_tax_compensation(employee_totals, employee, rule_totals, categories_totals, period_end_date=self.period_end_date)
                Form2316._calculate_supplementary_amounts(employee_totals, employee, rule_totals, categories_totals)
                Form2316._calculate_summary_data(employee_totals, employee, categories_totals, period_end_date=self.period_end_date)

                employee_data = self._prepare_employee_dat_line(employee, employee_rendering_data, employee_totals, dec_tax_total, categories_totals['TAX_ANN']["total"], i, schedule)
                # Accumulate a total dict with the values from the employees for the control line.
                schedule_totals.update({key: val for key, val in employee_data.items() if isinstance(val, (float, int))})
                dat_data_lines.append(','.join(self._format_value(value) for value in employee_data.values()))
            dat_data_lines.append(','.join(self._format_value(value) for value in self._prepare_schedule_control_line(schedule_totals, schedule)))

        attachment = self.env['ir.attachment'].create({
            'name': f"{company_tin}{company_branch_code}{self.period_end_date.strftime("%m%d%Y")}1604C.dat",
            'raw': '\n'.join(dat_data_lines).encode(),
            'res_model': self._name,
            'res_id': self.id,
        })
        return attachment

    def _prepare_employee_dat_line(self, employee, employee_rendering_data, employee_totals, dec_tax_total, tax_annualization_amount, sequence, schedule_number):
        """
        Prepare a line in the DAT file.
        Built to support both schedule at once.

        The data is returned as a dict to facilitate building the total control line later on.
        """
        self.ensure_one()
        prev_employment = self._get_previous_employment(employee)

        # To avoid yet another field, and because we can map it, we use a rule param for the region number.
        region_mapping = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_ph_hr_payroll_rdo_regions', self.period_end_date)

        # Unlike 2316, this report actually asks for tax amounts in more details, requiring us to recalculate them a bit.
        net_dec_tax_withheld = abs(dec_tax_total['total']) - tax_annualization_amount
        tax_withheld_jan_nov = abs(employee_totals['item_25a']) - net_dec_tax_withheld

        adjustment_needed = employee_totals['item_24'] - employee_totals['item_25b'] - tax_withheld_jan_nov
        if adjustment_needed > 0:
            tax_dec = adjustment_needed
            tax_refunded = 0.0
        else:
            tax_dec = 0.0
            tax_refunded = abs(adjustment_needed)

        employee_branch_code = (employee_rendering_data['employee_branch_code'] or '').lstrip('0').zfill(4)[:4]
        employer_branch_code = (employee_rendering_data['employer_branch_code'] or '').lstrip('0').zfill(4)[:4]
        employee_dat_line = {
            'schedule_number': schedule_number,                                                                         # Schedule number
            'form_type': '1604C',                                                                                       # Form type
            'employer_tin': employee_rendering_data['employer_tin'],                                                    # Employer's TIN
            'employer_branch_code': employer_branch_code,                                                               # Employer's Branch Code
            'return_period': self.period_end_date.strftime("%m/%d/%Y"),                                                 # Return period
            'sequence_number': str(sequence),                                                                           # Sequence number
            'employee_tin': employee_rendering_data['employee_tin'],                                                    # Employee's TIN
            'employee_branch_code': employee_branch_code,                                                               # Employee's Branch Code
            'employee_last_name': employee_rendering_data['employee_last_name'],                                        # Employee's Last Name
            'employee_first_name': employee_rendering_data['employee_first_name'],                                      # Employee's First Name
            'employee_middle_name': employee_rendering_data['employee_middle_name'] or '',                              # Employee's Middle Name
            'region_assigned': region_mapping.get(employee_rendering_data['employee_rdo_code'], ''),                    # Region number where assigned
            'prev_gross_compensation': prev_employment.nontaxable_income + prev_employment.taxable_income,              # Gross Compensation Income from Previous Employer
            'prev_nontax_basic_mwe': prev_employment.nontax_basic_mwe,                                                  # Basic/Statutory Minimum Wage from Previous Employer
        }
        if schedule_number == 'D1':
            employee_dat_line.update({
                'prev_nontax_13th_month': prev_employment.nontax_13th_month,                                            # Non-Taxable 13th month pay and other benefits from previous employer
                'prev_nontax_de_minimis': prev_employment.nontax_de_minimis,                                            # Non-Taxable De Minimis Benefits from previous employer
                'prev_nontax_statutory_contributions': prev_employment.nontax_statutory_contributions,                  # Non-Taxable SSS, GSIS, PAGIBIG and Union dues from previous employer
                'prev_nontax_salaries_other': (
                    prev_employment.nontax_salaries_other
                    + prev_employment.holiday_pay
                    + prev_employment.overtime_pay
                    + prev_employment.night_shift_differential
                    + prev_employment.hazard_pay
                ),                                                                                                      # Non-Taxable Salaries and Other Compensation from previous employer
                'prev_total_nontax_compensation': prev_employment.nontaxable_income,                                    # Total Non-Taxable/Exempt Compensation Income
                'prev_taxable_basic_salary': prev_employment.taxable_basic_salary,                                      # Taxable basic salary from previous employer
                'prev_taxable_13th_month': prev_employment.taxable_13th_month,                                          # Taxable 13th month pay and other benefits from previous employer
                'prev_taxable_salaries_other': prev_employment.taxable_salaries_other,                                  # Taxable Salaries and Other Compensation from previous employer
                'prev_total_taxable_income': prev_employment.taxable_income,                                            # Total Taxable from previous employer
                'present_employment_from': self._get_effective_period_start_date(employee).strftime("%m/%d/%Y"),        # Present Employment From
                'present_employment_to': self._get_effective_period_end_date(employee).strftime("%m/%d/%Y"),            # Present Employment To
                'pres_nontax_gross_compensation': employee_totals['item_19'],                                           # Non-Taxable Gross Compensation Income from present employer
                'pres_nontax_basic_salary': employee_totals['item_29'],                                                 # Non-Taxable basic salary from present employer
                'pres_nontax_13th_month': employee_totals['item_34'],                                                   # Total Non-Taxable 13th Month pay and Other Benefits from present employer
                'pres_nontax_de_minimis': employee_totals['item_35'],                                                   # Non-Taxable De Minimis Benefits from present employer
                'pres_nontax_statutory_contributions': employee_totals['item_36'],                                      # Non-Taxable SSS, GSIS, PAGIBIG and Union dues from present employer
                'pres_nontax_salaries_other': employee_totals['item_37'],                                               # Total Non-Taxable Salaries and other Compensation from present employer
                'pres_total_nontax_compensation': employee_totals['item_38'],                                           # Total Non-Taxable/Exempt Compensation Income from Present Employer
                'pres_taxable_basic_salary': employee_totals['item_39'],                                                # Taxable basic salary from present employer
                'pres_taxable_13th_month': employee_totals['item_48'],                                                  # Taxable 13th month pay and other benefits from present employer
                'pres_taxable_salaries_other': employee_totals['item_52'] - employee_totals['item_48'] - employee_totals['item_39'],  # Total Taxable Salaries and Other Compensation from present employer
                'pres_total_taxable_compensation': employee_totals['item_21'],                                          # Total Taxable Compensation Income from present employer
                'total_taxable_compensation_combined': employee_totals['item_23'],                                      # Total Taxable Compensation Income (Previous & Present Employers)
                'net_taxable_compensation': employee_totals['item_23'],                                                 # Net Taxable Compensation Income
                'tax_due': employee_totals['item_24'],                                                                  # Amount of Tax Due
                'tax_withheld_prev': employee_totals['item_25b'],                                                       # Amount Withheld by Previous Employer
                'tax_withheld_pres': tax_withheld_jan_nov,                                                              # Amount Withheld by Present Employer
                'tax_withheld_dec': tax_dec,                                                                            # Amound Withheld and paid in December
                'tax_refunded': tax_refunded,                                                                           # Over Withheld Tax Refunded to employee
                'tax_withheld_actual': employee_totals['item_24'],                                                      # Actual Amount Withheld
                'employee_nationality': employee.nationality_country_code,                                              # Employee's Nationality
                'employment_status': employee.employee_type_id.code or '',                                              # Current Employment Status
                'reason_of_separation': employee.departure_reason_id.l10n_ph_hr_payroll_bir_separation_code or 'NA',    # Reason of Separation
                'substituted_filing': 'No',                                                                             # Substituted Filing - Unsupported yet
                'pera_tax_credit': employee_totals['item_27'],                                                          # 5% Tax Credit (PERA Act of 2008) - Unsupported yet
            })
        else:
            employee_dat_line.update({
                'prev_holiday_pay': prev_employment.holiday_pay,                                                        # Holiday Pay from Previous Employer
                'prev_overtime_pay': prev_employment.overtime_pay,                                                      # Overtime Pay from Previous Employer
                'prev_night_differential': prev_employment.night_shift_differential,                                    # Night Shift Differential from Previous Employer
                'prev_hazard_pay': prev_employment.hazard_pay,                                                          # Hazard Pay from Previous Employer
                'prev_nontax_13th_month': prev_employment.nontax_13th_month,                                            # Non-Taxable 13th month pay and other benefits from previous employer
                'prev_nontax_de_minimis': prev_employment.nontax_de_minimis,                                            # Non-Taxable De Minimis Benefits from previous employer
                'prev_nontax_statutory_contributions': prev_employment.nontax_statutory_contributions,                  # Non-Taxable SSS, GSIS, PAGIBIG and Union dues from previous employer
                'prev_nontax_salaries_other': prev_employment.nontax_salaries_other,                                    # Non-Taxable Salaries and Other Compensation from previous employer
                'prev_total_nontax_compensation': prev_employment.nontaxable_income,                                    # Total Non-Taxable/Exempt Compensation Income
                'prev_taxable_13th_month': prev_employment.taxable_13th_month,                                          # Taxable 13th month pay and other benefits from previous employer
                'prev_taxable_salaries_other': prev_employment.taxable_salaries_other + prev_employment.taxable_basic_salary,  # Taxable Salaries and Other Compensation from previous employer
                'prev_total_taxable_income': prev_employment.taxable_income,                                            # Total Taxable from previous employer
                'present_employment_from': self._get_effective_period_start_date(employee).strftime("%m/%d/%Y"),        # Present Employment From
                'present_employment_to': self._get_effective_period_end_date(employee).strftime("%m/%d/%Y"),            # Present Employment To
                'pres_nontax_gross_compensation': employee_totals['item_19'] - employee_totals['item_36'],              # Non-Taxable Gross Compensation Income from present employer
                'pres_mwe_wage_day': employee_rendering_data['employee_stat_min_wage_day'],                             # Basic/Statutory Minimum Wage Per Day from Present Employer
                'pres_mwe_wage_month': employee_rendering_data['employee_stat_min_wage_month'],                         # Basic/Statutory Minimum Wage Per Month from Present Employer
                'pres_mwe_wage_year': employee.version_id._l10n_ph_hr_payroll_from_to_schedule(
                    employee.work_location_id.l10n_ph_hr_payroll_min_daily_wage, from_schedule='daily', to_schedule='yearly',
                ),                                                                                                      # Basic/Statutory Minimum Wage Per Year from Present Employer
                'factor_used': employee.version_id._l10n_ph_hr_payroll_get_employee_eemr_factor(),                                 # Factor Used (No. of Days/Year)
                'pres_holiday_pay': employee_totals['item_30'],                                                         # Holiday Pay from Present Employer
                'pres_overtime_pay': employee_totals['item_31'],                                                        # Overtime Pay from Present Employer
                'pres_night_differential': employee_totals['item_32'],                                                  # Night Shift Differential from Present Employer
                'pres_hazard_pay': employee_totals['item_33'],                                                          # Hazard Pay from Present Employer
                'pres_nontax_13th_month': employee_totals['item_34'],                                                   # Total Non-Taxable 13th Month pay and Other Benefits from present employer
                'pres_nontax_de_minimis': employee_totals['item_35'],                                                   # Non-Taxable De Minimis Benefits from present employer
                'pres_nontax_statutory_contributions': employee_totals['item_36'],                                      # Non-Taxable SSS, GSIS, PAGIBIG and Union dues from present employer
                'pres_nontax_salaries_other': employee_totals['item_37'],                                               # Total Non-Taxable Salaries and other Compensation from present employer
                'pres_total_nontax_compensation': employee_totals['item_38'] - employee_totals['item_36'],              # Total Non-Taxable/Exempt Compensation Income from Present Employer
                'pres_taxable_13th_month': employee_totals['item_48'],                                                  # Taxable 13th month pay and other benefits from present employer
                'pres_taxable_salaries_other': employee_totals['item_52'] - employee_totals['item_48'] - employee_totals['item_39'],  # Total Taxable Salaries and Other Compensation from present employer
                'pres_total_taxable_compensation': employee_totals['item_21'],                                          # Total Taxable Compensation Income from present employer
                'total_taxable_compensation_combined': employee_totals['item_23'],                                      # Total Taxable Compensation Income (Previous & Present Employers)
                'net_taxable_compensation': employee_totals['item_23'],                                                 # Net Taxable Compensation Income
                'tax_due': employee_totals['item_24'],                                                                  # Amount of Tax Due
                'tax_withheld_prev': employee_totals['item_25b'],                                                       # Amount Withheld by Previous Employer
                'tax_withheld_pres': tax_withheld_jan_nov,                                                              # Amount Withheld by Present Employer
                'tax_withheld_dec': tax_dec,                                                                            # Amound Withheld and paid in December
                'tax_refunded': tax_refunded,                                                                           # Over Withheld Tax Refunded to employee
                'tax_withheld_actual': employee_totals['item_24'],                                                      # Actual Amount Withheld
                'employee_nationality': employee.nationality_country_code,                                              # Employee's Nationality
                'employment_status': employee.employee_type_id.code or '',                                              # Current Employment Status
                'reason_of_separation': employee.departure_reason_id.l10n_ph_hr_payroll_bir_separation_code or 'NA',    # Reason of Separation
                'substituted_filing': 'No',                                                                             # Substituted Filing - Unsupported yet
                'pera_tax_credit': employee_totals['item_27'],                                                          # 5% Tax Credit (PERA Act of 2008) - Unsupported yet
                'pres_mwe_wage_net': employee_totals['item_29'] - employee_totals['item_36'],                           # Basic Statutory Min. wage (Net of SS/GSIS, PHIC, HDMF, Union Dues)
            })
        return employee_dat_line

    def _prepare_schedule_control_line(self, schedule_totals, schedule_number):
        """ Prepare the control line for a given schedule, based on the accumulated totals. """
        self.ensure_one()
        control_number = 'C1' if schedule_number == 'D1' else 'C2'

        company_tin = self.company_id.vat and self.company_id.vat.replace('-', '').replace(' ', '')[:9] or ''
        company_branch_code = (self.company_id.l10n_ph_branch_code or '').lstrip('0').zfill(4)[:4]
        if schedule_number == 'D1':
            control_line = [
                control_number,                                                                                         # Schedule number
                '1604C',                                                                                                # Form type
                company_tin,                                                                                            # Employer's TIN
                company_branch_code,                                                                                    # Employer's Branch Code
                self.period_end_date.strftime("%m/%d/%Y"),                                                              # Return Period
                schedule_totals['prev_gross_compensation'],                                                             # Gross Compensation Income from Previous Employer
                schedule_totals['prev_nontax_basic_mwe'],                                                               # Basic/Statutory Minimum Wage from Previous Employer
                schedule_totals['prev_nontax_13th_month'],                                                              # Non-Taxable 13th Month Pay and Other Benefits from Previous Employer
                schedule_totals['prev_nontax_de_minimis'],                                                              # Non-Taxable De Minimis Benefits from Previous Employer
                schedule_totals['prev_nontax_statutory_contributions'],                                                 # Non-Taxable SSS, GSIS, PAGIBIG and Union Dues from Previous Employer
                schedule_totals['prev_nontax_salaries_other'],                                                          # Non-Taxable Salaries and Other Compensation Benefits from Previous Employer
                schedule_totals['prev_total_nontax_compensation'],                                                      # Total Non-Taxable/Exempt Compensation Income from Previous Employer
                schedule_totals['prev_taxable_basic_salary'],                                                           # Total Taxable Basic Salary from Previous Employer
                schedule_totals['prev_taxable_13th_month'],                                                             # Taxable 13th Month Pay and Other Compensation Benefits from Previous Employer
                schedule_totals['prev_taxable_salaries_other'],                                                         # Taxable Salaries and other Compensation Benefits from Previous Employer
                schedule_totals['prev_total_taxable_income'],                                                           # Total Taxable Compensation Income from Previous Employer
                schedule_totals['pres_nontax_gross_compensation'],                                                      # Total Non-Taxable Gross Compensation Income from Present Employer
                schedule_totals['pres_nontax_basic_salary'],                                                            # Total Non-Taxable Basic Salary from Present Employer
                schedule_totals['pres_nontax_13th_month'],                                                              # Total Non-Taxable 13th Month Pay and Other Benefits from Present Employer
                schedule_totals['pres_nontax_de_minimis'],                                                              # Total Non-Taxable De Minimis Benefits from Present Employer
                schedule_totals['pres_nontax_statutory_contributions'],                                                 # Total Non-Taxable SSS, GSIS, PAGIBIG and Union Dues from Present Employer
                schedule_totals['pres_nontax_salaries_other'],                                                          # Total Non-Taxable Salaries and Other Compensation from Present Employer
                schedule_totals['pres_total_nontax_compensation'],                                                      # Total Non-Taxable/Exempt Compensation Income from Present Employer
                schedule_totals['pres_taxable_basic_salary'],                                                           # Total Taxable Basic Salary from Present Employer
                schedule_totals['pres_taxable_13th_month'],                                                             # Total Taxable 13th Month Pay and Other Benefits from Present Employer
                schedule_totals['pres_taxable_salaries_other'],                                                         # Total Taxable Salaries and Other Compensation Income from Present Employer
                schedule_totals['pres_total_taxable_compensation'],                                                     # Total Taxable Compensation Income from Present Employer
                schedule_totals['total_taxable_compensation_combined'],                                                 # Total Compensation Income (Previous and Present Employers)
                schedule_totals['net_taxable_compensation'],                                                            # Total Net Taxable Compensation Income
                schedule_totals['tax_due'],                                                                             # Total Amount Due
                schedule_totals['tax_withheld_prev'],                                                                   # Total Amount Withheld by Previous Employer
                schedule_totals['tax_withheld_pres'],                                                                   # Total Amount Withheld by Present Employer
                schedule_totals['tax_withheld_dec'],                                                                    # Total Amount Withheld and paid in December
                schedule_totals['tax_refunded'],                                                                        # Total Over Withheld tax refunded to employee
                schedule_totals['tax_withheld_actual'],                                                                 # Total Actual Amount Withheld
                schedule_totals['pera_tax_credit'],                                                                     # 5% Tax Credit (PERA Act of 2008)
            ]
        else:
            control_line = [
                control_number,                                                                                         # Schedule number
                '1604C',                                                                                                # Form type
                company_tin,                                                                                            # Employer's TIN
                company_branch_code,                                                                                    # Employer's Branch Code
                self.period_end_date.strftime("%m/%d/%Y"),                                                              # Return Period
                schedule_totals['prev_gross_compensation'],                                                             # Gross Compensation Income from Previous Employer
                schedule_totals['prev_nontax_basic_mwe'],                                                               # Basic/Statutory Minimum Wage from Previous Employer
                schedule_totals['prev_holiday_pay'],                                                                    # Holiday Pay from Previous Employer
                schedule_totals['prev_overtime_pay'],                                                                   # Overtime Pay from Previous Employer
                schedule_totals['prev_night_differential'],                                                             # Night Shift Differential from Previous Employer
                schedule_totals['prev_hazard_pay'],                                                                     # Hazard Pay from Previous Employer
                schedule_totals['prev_nontax_13th_month'],                                                              # Non-Taxable 13th Month Pay and Other Benefits from Previous Employer
                schedule_totals['prev_nontax_de_minimis'],                                                              # Non-Taxable De Minimis Benefits from Previous Employer
                schedule_totals['prev_nontax_statutory_contributions'],                                                 # Non-Taxable SSS, GSIS, PAGIBIG and Union Dues from Previous Employer
                schedule_totals['prev_nontax_salaries_other'],                                                          # Non-Taxable Salaries and Other Compensation Benefits from Previous Employer
                schedule_totals['prev_total_nontax_compensation'],                                                      # Total Non-Taxable/Exempt Compensation Income from Previous Employer
                schedule_totals['prev_taxable_13th_month'],                                                             # Taxable 13th Month Pay and Other Compensation Benefits from Previous Employer
                schedule_totals['prev_taxable_salaries_other'],                                                         # Taxable Salaries and other Compensation Benefits from Previous Employer
                schedule_totals['prev_total_taxable_income'],                                                           # Total Taxable Compensation Income from Previous Employer
                schedule_totals['pres_nontax_gross_compensation'],                                                      # Total Non-Taxable Gross Compensation Income from Present Employer
                schedule_totals['pres_mwe_wage_day'],                                                                   # Basic/Statutory Minimum Wage Per Day from Present Employer
                schedule_totals['pres_mwe_wage_month'],                                                                 # Basic/Statutory Minimum Wage Per Month from Present Employer
                schedule_totals['pres_mwe_wage_year'],                                                                  # Basic/Statutory Minimum Wage Per Year from Present Employer
                schedule_totals['pres_holiday_pay'],                                                                    # Holiday Pay from Present Employer
                schedule_totals['pres_overtime_pay'],                                                                    # Overtime Pay from Present Employer
                schedule_totals['pres_night_differential'],                                                             # Night Shift Differential from Present Employer
                schedule_totals['pres_hazard_pay'],                                                                     # Hazard Pay from Present Employer
                schedule_totals['pres_nontax_13th_month'],                                                              # Total Non-Taxable 13th Month Pay and Other Benefits from Present Employer
                schedule_totals['pres_nontax_de_minimis'],                                                              # Total Non-Taxable De Minimis Benefits from Present Employer
                schedule_totals['pres_nontax_statutory_contributions'],                                                 # Total Non-Taxable SSS, GSIS, PAGIBIG and Union Dues from Present Employer
                schedule_totals['pres_nontax_salaries_other'],                                                          # Total Non-Taxable Salaries and Other Compensation from Present Employer
                schedule_totals['pres_total_nontax_compensation'],                                                      # Total Non-Taxable/Exempt Compensation Income from Present Employer
                schedule_totals['pres_taxable_13th_month'],                                                             # Total Taxable 13th Month Pay and Other Benefits from Present Employer
                schedule_totals['pres_taxable_salaries_other'],                                                         # Total Taxable Salaries and Other Compensation Income from Present Employer
                schedule_totals['pres_total_taxable_compensation'],                                                     # Total Taxable Compensation Income from Present Employer
                schedule_totals['total_taxable_compensation_combined'],                                                 # Total Compensation Income (Previous and Present Employers)
                schedule_totals['net_taxable_compensation'],                                                            # Total Net Taxable Compensation Income
                schedule_totals['tax_due'],                                                                             # Total Amount Due
                schedule_totals['tax_withheld_prev'],                                                                   # Total Amount Withheld by Previous Employer
                schedule_totals['tax_withheld_pres'],                                                                   # Total Amount Withheld by Present Employer
                schedule_totals['tax_withheld_dec'],                                                                    # Total Amount Withheld and paid in December
                schedule_totals['tax_refunded'],                                                                        # Total Over Withheld tax refunded to employee
                schedule_totals['tax_withheld_actual'],                                                                 # Total Actual Amount Withheld
                schedule_totals['pera_tax_credit'],                                                                     # 5% Tax Credit (PERA Act of 2008)
                schedule_totals['pres_mwe_wage_net']                                                                    # Basic Statutory Min. wage (Net of SS/GSIS, PHIC, HDMF, Union Dues)
            ]
        return control_line
