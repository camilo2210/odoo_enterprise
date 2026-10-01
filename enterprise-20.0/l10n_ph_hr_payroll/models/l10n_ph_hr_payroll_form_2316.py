# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from odoo.fields import Domain
from odoo.tools import plaintext2html

from odoo import api, fields, models


class L10nPhHrPayrollForm2316(models.Model):
    _name = 'l10n_ph_hr_payroll.form_2316'
    _inherit = 'l10n_ph_hr_payroll.declaration'
    _description = 'Form 2316'

    period_start_date = fields.Date(
        default=lambda s: fields.Date.today() + relativedelta(day=1, month=1, years=-1),
    )
    period_end_date = fields.Date(
        default=lambda s: fields.Date.today() + relativedelta(day=31, month=12, years=-1),
    )
    employer_signatory_name = fields.Char(
        default=lambda self: self.env.company.display_name,
    )
    departing_employees_only = fields.Boolean(
        string="Only Departing Employees",
        help="Only select departing employees when generating the declarations.",
    )

    period_1604c_declaration_id = fields.Many2one(
        comodel_name='l10n_ph_hr_payroll.form_1604c',
    )

    def _get_report_version_domain(self):
        """
        Build the search domain to find employee contract versions for this report.

        This identifies all employees who had a validated/paid payslip during the
        report period, and further ensures their contract dates actively overlap
        with the period.
        """
        self.ensure_one()
        domain = super()._get_report_version_domain()
        if self.departing_employees_only:
            domain = Domain.AND([domain, [('departure_date', '!=', False)]])
        return domain

    def _get_declaration_name(self):
        self.ensure_one()
        return self.env._("Form 2316")

    def _get_pdf_report(self):
        return self.env.ref('l10n_ph_hr_payroll.action_l10n_ph_hr_payroll_report_employee_2316')

    def _validate_employee_data(self, employees, rendering_data):
        """ This won't look very pretty, but we'll gather the errors to print them in the chatter. """
        self.ensure_one()
        for employee in employees:
            errors = []
            if not employee.l10n_ph_hr_payroll_work_tin:
                errors.append(self.env._("The TIN number is not set."))
            if not employee.legal_name:
                errors.append(self.env._("The Name is not set."))
            if not employee.l10n_ph_hr_payroll_rdo_code:
                errors.append(self.env._("The RDO Code is not set."))
            if not employee.private_street and not employee.l10n_ph_hr_payroll_registered_address:
                errors.append(self.env._("The Address is not set."))
            if employee.l10n_ph_hr_payroll_registered_address and not employee.l10n_ph_hr_payroll_registered_zip:
                errors.append(self.env._("The Registered ZIP is not set."))
            if not employee.l10n_ph_hr_payroll_registered_address and not employee.private_zip:
                errors.append(self.env._("The Private ZIP is not set."))
            if not employee.birthday:
                errors.append(self.env._("The Birthday is not set."))
            if not employee.company_id.vat:
                errors.append(self.env._("The Employer's TIN is not set."))
            if not employee.company_id.name:
                errors.append(self.env._("The Employer's Name is not set."))
            if not employee.company_id.street:
                errors.append(self.env._("The Employer's Address is not set."))
            if not employee.company_id.zip:
                errors.append(self.env._("The Employer's ZIP is not set."))
            if employee.l10n_ph_hr_payroll_minimum_wage_earner and not employee.work_location_id.l10n_ph_hr_payroll_min_daily_wage:
                errors.append(self.env._("The Daily Minimum Wage is not set."))

            if prev_employment := self._get_previous_employment(employee):
                if not prev_employment.tin:
                    errors.append(self.env._("The Previous Employer's TIN is not set."))
                if not prev_employment.name:
                    errors.append(self.env._("The Previous Employer's Name is not set."))
                if not prev_employment.address:
                    errors.append(self.env._("The Previous Employer's Address is not set."))
                if not prev_employment.zip:
                    errors.append(self.env._("The Previous Employer's ZIP is not set."))

            if errors:
                rendering_data["employees_with_error"][employee] = '\n'.join(errors)

    def _get_rendering_data(self, employees):
        rendering_data = {
            'employees_with_error': {}
        }
        # Start by validating the employees
        self._validate_employee_data(employees, rendering_data)

        structures = self._get_relevant_structures()
        all_payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', self.period_start_date),
            ('date_to', '<=', self.period_end_date),
            ('employee_id', 'in', employees.ids),
            ('struct_id', 'in', structures.ids),
            ('company_id', '=', self.company_id.id),
        ]).grouped('employee_id')

        for employee in employees:
            if employee in rendering_data['employees_with_error']:
                continue
            employee_payslips = all_payslips.get(employee, self.env['hr.payslip'])
            all_lines_values = employee_payslips._get_line_values(set(employee_payslips.line_ids.mapped('code')), vals_list=['total', 'ytd'], compute_sum=True)
            rule_totals, categories_totals = employee_payslips._l10n_ph_hr_payroll_aggregate_totals(all_lines_values)
            employee_rendering_data = {}
            # Fill the data one section at a time.
            self._add_report_data(employee_rendering_data, employee)
            self._add_employee_data(employee_rendering_data, employee)
            self._add_current_employer_data(employee_rendering_data, employee)
            self._add_previous_employer_data(employee_rendering_data, employee)
            # Prepare all the totals separately.
            # We will store the raw amounts and format before adding to the rendering data.
            employee_totals = defaultdict(float)
            self._calculate_non_tax_compensation(employee_totals, employee, rule_totals, categories_totals)
            self._calculate_tax_compensation(employee_totals, employee, rule_totals, categories_totals)
            self._calculate_supplementary_amounts(employee_totals, employee, rule_totals, categories_totals)
            self._calculate_summary_data(employee_totals, employee, categories_totals)

            rendering_data[employee] = {
                k: self._format_value(v) for k, v in (employee_rendering_data | employee_totals).items()
            }
        # It is cleaner to check the declarations directly, but this gives broad directions into what to fix.
        if len(rendering_data['employees_with_error']) > 0:
            employee_errors = rendering_data['employees_with_error']
            error_message = self.env._(
                "Some employee's declaration couldn't be generated. Please fix the following employee's errors:\n%(errors)s",
                errors='\n'.join([f"{employee.name}:\n- {errors.replace('\n', '\n- ')}" for employee, errors in employee_errors.items()])
            )
            self._message_log(body=plaintext2html(error_message))
        return rendering_data

    def _add_report_data(self, employee_rendering_data, employee):
        self.ensure_one()
        employee_rendering_data.update({
            'year': str(self.period_end_date.year),
            'period_from': self._get_effective_period_start_date(employee).strftime("%m/%d"),
            'period_to': self._get_effective_period_end_date(employee).strftime("%m/%d"),
            'employer_signatory_name': self.employer_signatory_name,
        })

    def _add_employee_data(self, employee_rendering_data, employee):
        employee.ensure_one()
        local_address = ", ".join(list(filter(None, [
            employee.private_street,
            employee.private_street2 or '',
            employee.private_city,
            employee.private_state_id.name,
        ]))) if employee.private_country_id.code == 'PH' else ''
        # Parse and format the phone number of the employee. Looks at the employee's country with a fallback to its company's
        employee_phone = self._get_formated_phone_number(employee)

        formatted_name = employee.l10n_ph_legal_last_name
        if employee.l10n_ph_legal_first_name:
            formatted_name += f", {employee.l10n_ph_legal_first_name}"
        if employee.l10n_ph_legal_middle_name:
            formatted_name += f" {employee.l10n_ph_legal_middle_name}"

        tin = employee.l10n_ph_hr_payroll_work_tin
        employee_rendering_data.update({
            'employee_tin': tin and tin.replace('-', '').replace(' ', '')[:9] or '',
            'employee_branch_code': employee.l10n_ph_hr_payroll_work_tin_branch_code or '',
            'employee_formatted_name': formatted_name,
            'employee_legal_name': employee.legal_name,
            'employee_first_name': employee.l10n_ph_legal_first_name,
            'employee_middle_name': employee.l10n_ph_legal_middle_name,
            'employee_last_name': employee.l10n_ph_legal_last_name,
            'employee_rdo_code': employee.l10n_ph_hr_payroll_rdo_code,
            'employee_registered_address': employee.l10n_ph_hr_payroll_registered_address or local_address,
            'employee_registered_zip': employee.l10n_ph_hr_payroll_registered_zip or employee.private_zip,
            # Only show the local address (private address) if it was not used as registered address.
            'employee_local_home_address': employee.l10n_ph_hr_payroll_registered_address and local_address or '',
            'employee_local_home_zip': employee.private_zip if employee.l10n_ph_hr_payroll_registered_address and local_address else '',
            'employee_foreign_address': employee.l10n_ph_hr_payroll_foreign_address,
            'employee_dob': employee.birthday and employee.birthday.strftime("%m/%d/%Y"),
            'employee_contact_number': employee_phone,
            'employee_stat_min_wage_day': 0.0,
            'employee_stat_min_wage_month': 0.0,
            'employee_is_mwe': False,
        })
        if employee.l10n_ph_hr_payroll_minimum_wage_earner:
            min_wage = employee.work_location_id.l10n_ph_hr_payroll_min_daily_wage
            employee_rendering_data.update({
                'employee_stat_min_wage_day': min_wage,
                'employee_stat_min_wage_month': employee.version_id._l10n_ph_hr_payroll_from_to_schedule(
                    min_wage, from_schedule='daily', to_schedule='monthly'
                ),
                'employee_is_mwe': True,
            })

    def _add_current_employer_data(self, employee_rendering_data, employee):
        employee.ensure_one()
        registered_address = ", ".join(list(filter(None, [
            employee.company_id.street,
            employee.company_id.street2 or '',
            employee.company_id.city,
            employee.company_id.state_id.name or '',
        ])))
        tin = employee.company_id.vat
        employee_rendering_data.update({
            'employer_tin': tin and tin.replace('-', '').replace(' ', '')[:9] or '',
            'employer_branch_code': employee.company_id.l10n_ph_branch_code,
            'employer_name': employee.company_id.name,
            'employer_registered_address': registered_address,
            'employer_zip': employee.company_id.zip,
            'employer_is_main': employee.l10n_ph_hr_payroll_is_main_employment,
        })

    def _add_previous_employer_data(self, employee_rendering_data, employee, period_end_date=None):
        employee.ensure_one()
        prev_employment = self._get_previous_employment(employee, period_end_date)
        employee_rendering_data.update({
            'employer_previous_tin': (prev_employment.tin or '').replace('-', '').replace(' ', ''),
            'employer_previous_name': prev_employment.name or '',
            'employer_previous_address': prev_employment.address or '',
            'employer_previous_zip': prev_employment.zip or '',
        })

    def _calculate_summary_data(self, employee_rendering_data, employee, categories_totals, period_end_date=None):
        employee.ensure_one()

        prev_employment = self._get_previous_employment(employee, period_end_date)
        employee_rendering_data.update({
            'item_19': employee_rendering_data['item_38'] + employee_rendering_data['item_52'],
            'item_20': employee_rendering_data['item_38'],
            'item_22': prev_employment.taxable_income,
            'item_25a': categories_totals['TAX']['total'],
            'item_25b': prev_employment.tax_withheld,
            # Note: we do not support PERA yet, but we can leave a hypotetical total here in case a user wish to add a category and rule for it
            'item_27': categories_totals['PERA']['total'],
        })
        employee_rendering_data['item_21'] = employee_rendering_data['item_19'] - employee_rendering_data['item_20']
        employee_rendering_data['item_23'] = employee_rendering_data['item_21'] + employee_rendering_data['item_22']
        employee_rendering_data['item_24'] = self._recalculate_annual_tax_due(employee_rendering_data['item_23'], employee, period_end_date)
        # 25a is a negative amount, but 26 expects to sum the amounts in 25a and 25b as positive amounts
        employee_rendering_data['item_26'] = -employee_rendering_data['item_25a'] + employee_rendering_data['item_25b']
        employee_rendering_data['item_28'] = employee_rendering_data['item_26'] + employee_rendering_data['item_27']

    @api.model
    def _recalculate_annual_tax_due(self, gross_taxable_compensation_income, employee, period_end_date=None):
        """
        Calculate and return the total tax due for the whole year for the employee whose payslips are provided.

        Case 24 is the recalculated total tax due for the year.
        It needs to exactly match case 26; which is the total tax withheld after annualization.

        In theory, we could simply paste the same amount in both; but to be complete and avoid mistake it is best
        to recalculate and compare.
        """
        period_end_date = self._get_effective_period_end_date(employee, period_end_date)
        yearly_tax_table = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_ph_hr_payroll_tax_rates', period_end_date).get('yearly')
        total_tax_due = previous_ceiling = 0
        for ceiling, tax_rate, fixed_amount in yearly_tax_table:
            if ceiling is None or gross_taxable_compensation_income <= ceiling:
                excess = gross_taxable_compensation_income - previous_ceiling
                total_tax_due = fixed_amount + (excess * (tax_rate / 100.0))
                break
            previous_ceiling = ceiling
        return total_tax_due

    def _is_nmwe_basic_tax_exempt(self, employee, categories_totals, period_end_date=None):
        """ Return whether a non-MWE employee's yearly basic salary is at or below the yearly tax-exempt cap. """
        period_end_date = self._get_effective_period_end_date(employee, period_end_date)
        yearly_tax_table = self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_ph_hr_payroll_tax_rates', period_end_date
        ).get('yearly')
        exempt_cap = yearly_tax_table[0][0]
        return categories_totals['PH_BASIC']['nmwe'] <= exempt_cap

    def _calculate_non_tax_compensation(self, employee_totals, employee, rule_totals, categories_totals, period_end_date=None):
        employee.ensure_one()
        mwe_basic = categories_totals['PH_BASIC']['mwe'] + categories_totals['PRE_TAX_DEDUCTIONS']['mwe']
        nmwe_basic = categories_totals['PH_BASIC']['nmwe'] + categories_totals['PRE_TAX_DEDUCTIONS']['nmwe']
        non_tax_compensations = {
            'item_29': mwe_basic + (nmwe_basic if self._is_nmwe_basic_tax_exempt(employee, categories_totals, period_end_date) else 0.0),
            'item_30': categories_totals['HP']['mwe'],
            'item_31': categories_totals['OP']['mwe'],
            'item_32': categories_totals['NSD']['mwe'],
            'item_33': categories_totals['HAZARD']['mwe'],
            'item_34': rule_totals['OB'],  # Specifically the 90k capped OB rule
            'item_35': categories_totals['DE_MINIMIS']['total'],
            'item_36': abs(categories_totals['MANDATORY_CONTRIBUTIONS']['total']),
            'item_37': categories_totals['NT_ALW']['total'] + categories_totals['NT_BEN']['total'] - rule_totals['OB'] + categories_totals['NON_TAX_NON_CASH_EARNINGS']['total'] + categories_totals['ECOLA']['mwe'],
        }
        employee_totals.update({
            **non_tax_compensations,
            'item_38': sum(non_tax_compensations.values())
        })

    def _calculate_tax_compensation(self, employee_totals, employee, rule_totals, categories_totals, period_end_date=None):
        employee.ensure_one()
        is_rank_and_file = employee.l10n_ph_hr_payroll_employee_rank in (False, 'rank_and_file')
        # TOB is reported in item 48
        taxable_allowances = categories_totals['TA']['total'] - rule_totals['TOB']
        taxable_non_cash = categories_totals['TAX_NON_CASH_EARNINGS']['total']
        if is_rank_and_file:  # They do not benefit from 'tax-free' fringe benefits, so if any it falls in the tax totals.
            taxable_allowances += categories_totals['CASH_FRINGE_BENEFITS']['total']
            taxable_non_cash += categories_totals['NON_CASH_FRINGE_BENEFITS']['total']
        nmwe_basic = categories_totals['PH_BASIC']['nmwe'] + categories_totals['PRE_TAX_DEDUCTIONS']['nmwe']
        employee_totals.update({
            'item_39': 0.0 if self._is_nmwe_basic_tax_exempt(employee, categories_totals, period_end_date) else nmwe_basic,
            'item_40': categories_totals['REP']['total'] or None,  # hypothetical
            'item_41': categories_totals['TRANSP']['total'] or None,  # hypothetical
            'item_42': categories_totals['ECOLA']['nmwe'] or None,
            'item_43': categories_totals['HOUSING']['total'] or None,  # hypothetical
            'item_44a_label': 'Taxable Allowances' if taxable_allowances else '',
            'item_44a': taxable_allowances,
            'item_44b_label': 'Non-Cash Earnings' if taxable_non_cash else '',
            'item_44b': taxable_non_cash,
        })

    def _calculate_supplementary_amounts(self, employee_totals, employee, rule_totals, categories_totals):
        employee.ensure_one()
        employee_totals.update({
            'item_45': categories_totals['COMM']['total'] or None,  # hypothetical
            'item_46': categories_totals['PROFIT']['total'] or None,  # hypothetical
            'item_47': categories_totals['FEES']['total'] or None,  # hypothetical
            'item_48': rule_totals['TOB'],  # Specific rule
            'item_49': categories_totals['HAZARD']['nmwe'] or None,  # hypothetical
            'item_50': categories_totals['OP']['nmwe'] or None,  # hypothetical
            'item_51a_label': 'Holiday Pay' if categories_totals['HP']['nmwe'] else '',
            'item_51a': categories_totals['HP']['nmwe'],
            'item_51b_label': 'Night Shift Diff' if categories_totals['NSD']['nmwe'] else '',
            'item_51b': categories_totals['NSD']['nmwe'],
        })
        grand_total_items = {
            'item_39', 'item_40', 'item_41', 'item_42', 'item_43', 'item_44a', 'item_44b',
            'item_45', 'item_46', 'item_47', 'item_48', 'item_49', 'item_50', 'item_51a', 'item_51b',
        }
        employee_totals['item_52'] = sum(val for key, val in employee_totals.items() if key in grand_total_items and val is not None)

    @api.model
    def _get_formated_phone_number(self, employee):
        """
        Returns the employee's private phone number after trying to format it into its local equivalent.
        The formatting will look at the various countries linked to an employee in order to try and find one
        that is able to parse the number.
        """
        if not employee.private_phone:
            return ''

        employee_countries = self.env['res.country'].union({
            employee.country_id,
            employee.private_country_id,
            employee.company_id.country_id,
            employee.address_id.country_id,
        })
        # Always parse at least once
        employee_phone = employee.private_phone
        for i, country in enumerate(employee_countries):
            if i == 0 or '+' in employee_phone:
                employee_phone = employee._phone_format(
                    fname="private_phone",
                    force_format="NATIONAL",
                    country=country,
                )

        return (employee_phone or employee.private_phone).replace('-', '').replace('(', '').replace(')', '').replace(' ', '')

    def _get_pdf_filename(self, employee):
        """
        The format is mandated to be: Last Name_TIN_Period
        e.g. from the regulation: Dela Cruz_131885220000_12312014
        """
        self.ensure_one()
        period_end_date = self._get_effective_period_end_date(employee)
        return f"{employee.l10n_ph_legal_last_name}_{employee.l10n_ph_hr_payroll_work_tin.replace('-', '').replace(' ', '')[:9]}_{period_end_date.strftime("%m%d%Y")}.pdf"
