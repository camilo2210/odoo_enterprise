# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from datetime import datetime, date

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.float_utils import float_compare


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_hk_worked_days_leaves_count = fields.Integer(
        string='Worked Days Leaves Count',
        compute='_compute_worked_days_leaves_count',
    )
    l10n_hk_713_gross = fields.Monetary(
        string='713 Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_mpf_gross = fields.Monetary(
        string='MPF Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_autopay_gross = fields.Monetary(
        string='AutoPay Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_second_batch_autopay_gross = fields.Monetary(
        string='Second Batch AutoPay Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_average_daily_wage = fields.Monetary(
        string='Average Daily Wage',
        help='Calculated as per the Employment (Amendment) Ordinance 2007: (Total of fully paid wages earned in the 12-month period) / (Total number of fully paid days in that period).',
        compute='_compute_average_daily_wage',
    )
    l10n_hk_rental_id = fields.Many2one(
        comodel_name='l10n_hk.rental',
    )

    # Technical fields
    l10n_hk_contribution_line_id = fields.One2many(
        comodel_name='l10n_hk.empf.contribution.report.line',
        inverse_name='payslip_id',
        export_string_translation=False,
    )
    l10n_hk_version_scheme_id = fields.Many2one(
        related='version_id.l10n_hk_mpf_scheme_id',
        export_string_translation=False,
    )

    def _l10n_hk_filter_slips_requiring_reporting(self):
        """
        Helper that returns the payslips in self that requires to appear in the contribution report.
        In practice, ALL payslips for employees that are in age of contributing should return True, exceptions being:
        - Payslips for employees younger than 18 and that are not using VC
        - Payslips for employees that are older than 65 and that are not using VC
        - Payslips for employees that are exempt of MPF and are not using VC
        Some payslips without contributions need to be returned (we rely on of them for new register for example)
        """
        slips_to_report = self.env['hr.payslip']
        contribution_codes = ['EEMC', 'ERMC', 'EEVC', 'ERVC', 'ERVC2']
        payslip_values = self._get_line_values(contribution_codes)
        for slip in self:
            employee = slip.employee_id
            version = slip.version_id

            is_contributing = any(payslip_values[code][slip.id]['total'] for code in contribution_codes)
            is_of_age = not employee.birthday or employee.birthday < fields.Date.context_today(slip) - relativedelta(
                years=18)
            is_below_65 = not employee.birthday or employee.birthday > fields.Date.context_today(slip) - relativedelta(
                years=65)

            if is_contributing or (is_of_age and is_below_65 and not version.l10n_hk_mpf_exempt):
                slips_to_report |= slip

        return slips_to_report

    def _get_regular_wage_structures(self):
        """
        Retrieve regular wage structures used for ADW (Average Daily Wage) and 713 Ordinance calculations.
        This explicitly excludes termination payment structures, which legally must not inflate the historical wage base.
        """
        return self.env['hr.payroll.structure'].search([
            ('country_id', '=', self.env.ref('base.hk').id),
            ('l10n_hk_is_termination_pay', '=', False),
        ])

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_hk_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',

                'data/cap57/employee_salary_data.xml',
                'data/cap57/casual_employee_salary_data.xml',
                'data/cap57/non_employee_salary_data.xml',

                'data/hr_rule_parameters_data.xml',
                'data/l10n_hk.mpf.scheme.csv',
                'data/hr_payroll_warning_data.xml',
            ])]

    @api.depends('worked_days_line_ids')
    def _compute_worked_days_leaves_count(self):
        for payslip in self:
            payslip.l10n_hk_worked_days_leaves_count = len(payslip.worked_days_line_ids.filtered(lambda wd: wd.l10n_hk_leave_id))

    @api.depends('line_ids.total', 'struct_id')
    def _compute_gross(self):
        """
        Compute gross amounts at the time of this payslip.
        They will be made available in the Payroll Analysis report.
        """
        related_structs = self._get_regular_wage_structures()
        hk_slip = self.filtered(lambda s: s.struct_id in related_structs)
        line_values = hk_slip._get_line_values(['713_GROSS', 'GROSS', 'MEA', 'SBA'])
        for payslip in hk_slip:
            payslip.l10n_hk_713_gross = line_values['713_GROSS'][payslip.id]['total']
            payslip.l10n_hk_mpf_gross = line_values['GROSS'][payslip.id]['total']
            payslip.l10n_hk_autopay_gross = line_values['MEA'][payslip.id]['total']
            payslip.l10n_hk_second_batch_autopay_gross = line_values['SBA'][payslip.id]['total']

    @api.depends('input_line_ids', 'input_line_ids.amount')
    def _compute_average_daily_wage(self):
        """
        Calculate and return the Average Daily Wage (ADW), which is used to calculate payments for various statutory entitlements, including:
        - Holiday Pay
        - Annual Leave Pay
        - Sickness Allowance
        - Maternity and Paternity Leave Pay
        - Payment in lieu of notice

        The calculation is governed by the Employment (Amendment) Ordinance 2007:
            ADW = (Total wages earned in the 12-month period) / (Total number of days in that period)

        In order to be fair to the employee, the total wage calculation must exclude days for which the employee was not
        paid their full pay (sick leave,...) as well as the wages of these days.

        The period in which to look for the ADW is based on the last 365 days, and not the last 12 months.

        Example:
            Natalie Chan takes an annual leave from August 4, 2025, to August 6, 2025.
            The wages she received in the last 12 months are of HK350,000.
            During this period,she took 5 days of unpaid leave and 2 days of sickness leave (for which she was paid a total of HK1,500).

            The calculation should then be:
            - Disregard the days of leave not fully paid from the total calendar days.
            - Disregard the payments made for those specific leave days from the total wages.

            So the ADW is: (HK$350,000-HK$1,500) / (365 - 5 - 2) = HK$973.46
        :return: The ADW for the period.
        """
        for slip in self:
            if slip.country_code != 'HK' or not (slip.date_from and slip.date_to):
                slip.l10n_hk_average_daily_wage = 0
                continue

            adw = 0
            average_daily_wage = slip._get_input_line_amount('AVERAGE_DAILY_WAGE')
            if average_daily_wage:
                slip.l10n_hk_average_daily_wage = average_daily_wage
                continue

            last_year_payslips = slip._get_previous_year_payslips(order='date_from')
            if last_year_payslips:
                gross = last_year_payslips._get_line_values(['713_GROSS'], compute_sum=True)['713_GROSS']['sum']['total']
                gross -= last_year_payslips._get_total_non_full_pay()
                number_of_days = last_year_payslips._get_number_of_worked_days(only_full_pay=True)
                if number_of_days > 0:
                    adw = gross / number_of_days

            slip.l10n_hk_average_daily_wage = adw

    def _get_base_local_dict(self):
        """
        In Hong Kong, there are a few rules that are dependent on a monthly amount.
        While it works well in most cases; there is a case where a change in contract is done in the middle of a period.
        In this case, the payrun would contain two payslips for the same employee! To avoid counting twice the amounts,
        we need to know at the time of calculating the rule what has already been registered in these rules.
        Also provides the adjusted minimum and maximum relevant income for MPF calculations.
        """
        res = super()._get_base_local_dict()
        if self.struct_id.country_id.code != 'HK':
            return res

        worked_days_prorata_rate = 1
        total_days = sum(wd.number_of_days for wd in self.worked_days_line_ids)
        actual_work_days = self._get_number_of_worked_days()
        if total_days:
            worked_days_prorata_rate = actual_work_days / total_days

        minimum_relevant_income, maximum_relevant_income = self._l10n_hk_get_mpf_caps()
        res = {
            **res,
            **self._l10n_hk_aggregate_payrun_totals(),
            'worked_days_prorata_rate': worked_days_prorata_rate,
            'l10n_hk_mpf_minimum_relevant_income': minimum_relevant_income,
            'l10n_hk_mpf_maximum_relevant_income': maximum_relevant_income,
        }
        if self.struct_id.code == 'CAP57CASUAL':
            res["l10n_hk_gross_daily_wages"] = self._get_daily_gross_for_period()
        return res

    def _get_termination_pay_label(self, termination_reason_code, rule_type=None):
        """
        To reduce the size of the rule and avoid mistakes, the two termination payment types share the same rules.
        It works because the calculation is exactly the same; but the implications are different.
        To make it clear to the employer & employee we want to dynamically adjust the result name; but as translations
        wouldn't really work in salary rules we'll pass in the translated terms from a method.

        :return: The translated name to use for the given termination payment type and rule type.
        """
        if termination_reason_code in ('REDUNDANCY', 'LAID_OFF'):
            termination_pay_name = self.env._('Severance Payment')
        elif termination_reason_code in ('DEATH', 'DISMIS', 'CONTRACT_END', 'ILL_HEALTH', 'RETIRE'):
            termination_pay_name = self.env._('Long Service Payment')
        else:
            termination_pay_name = self.env._('Termination Payment')

        match rule_type:
            case 'pre_transition_payment':
                return self.env._('%(termination_pay_name)s - Pre-Transition', termination_pay_name=termination_pay_name)
            case 'post_transition_payment':
                return self.env._('%(termination_pay_name)s - Post-Transition', termination_pay_name=termination_pay_name)
            case 'pre_transition_offset':
                return self.env._('%(termination_pay_name)s - Pre-Transition Offset', termination_pay_name=termination_pay_name)
            case 'post_transition_offset':
                return self.env._('%(termination_pay_name)s - Post-Transition Offset', termination_pay_name=termination_pay_name)
            case _:
                return termination_pay_name

    def _l10n_hk_aggregate_payrun_totals(self):
        """
        Aggregates totals from previous payslips in the same batch to enforce statutory monthly caps
        (e.g., during mid-month contract splits).

        :return: Dict containing 'l10n_hk_payrun_totals' and 'l10n_hk_payrun_category_totals'
                 (defaulting to 0.0).
        """
        self.ensure_one()
        previous_slips = self.payslip_run_id.slip_ids.filtered_domain([
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('version_id.date_start', '<', self.version_id.date_start),
            ('struct_id.l10n_hk_is_termination_pay', '=', self.struct_id.l10n_hk_is_termination_pay),
        ])
        rules_totals, categories_totals = previous_slips._l10n_hk_aggregate_totals()
        return {
            'l10n_hk_payrun_totals': rules_totals,
            'l10n_hk_payrun_category_totals': categories_totals,
        }

    def _l10n_hk_aggregate_totals(self, line_values=None):
        """
        Aggregates monetary totals of salary rules and their hierarchical categories for payslips in self.

        This serves two main purposes:
        1. Enforcing statutory monthly caps (e.g., MPF) across multiple slips in a single payrun.
        2. Rolling up category totals for IRD tax reporting (IR56 forms).

        :param line_values: Optional pre-computed line values to save database queries.
        :return: A tuple of (rules_totals, categories_totals) as defaultdicts defaulting to 0.0.
        """
        rules_totals = defaultdict(float)
        categories_totals = defaultdict(float)

        if not line_values:
            line_values = self._get_line_values(set(self.line_ids.mapped('code')), compute_sum=True)

        category_mapping = self.struct_id._l10n_hk_get_rules_per_categories()
        for category_code, rule_codes in category_mapping.items():
            for rule_code in rule_codes:
                for payslip in self:
                    total = line_values.get(rule_code, {}).get(payslip.id, {}).get("total", 0.0)
                    categories_totals[category_code] += total
        # Keep rules_totals as a defaultdict defaulting to 0.0 for ease of writing rules.
        rules_totals.update({code: val['sum']['total'] for code, val in line_values.items()})
        return rules_totals, categories_totals

    def _l10n_hk_get_mpf_caps(self):
        """
        Provides the minimum and maximum relevant wages for MPF calculation based on the employee's pay schedule.
        The amounts can be controlled by using the rule parameters.

        PS: while we don't support schedule pays less frequent than monthly for now, it doesn't hurt to handle them here
        in case of future need.
        """
        self.ensure_one()
        schedule_pay = self.version_id.schedule_pay
        minimum_relevant_income = maximum_relevant_income = 0.0
        if schedule_pay == 'monthly':
            minimum_relevant_income = self._rule_parameter('l10n_hk_mpf_minimum_monthly_relevant_wage')
            maximum_relevant_income = self._rule_parameter('l10n_hk_mpf_maximum_monthly_relevant_wage')
        elif schedule_pay in ('annually', 'semi-annually', 'quarterly', 'bi-monthly'):
            months = {
                'bi-monthly': 2,
                'quarterly': 3,
                'semi-annually': 6,
                'annually': 12,
            }.get(schedule_pay, 1)
            minimum_relevant_income = self._rule_parameter('l10n_hk_mpf_minimum_monthly_relevant_wage') * months
            maximum_relevant_income = self._rule_parameter('l10n_hk_mpf_maximum_monthly_relevant_wage') * months
        elif schedule_pay in ('semi-monthly', 'bi-weekly', 'weekly', 'daily'):
            period_days = (self.date_to - self.date_from).days + 1
            minimum_relevant_income = self._rule_parameter('l10n_hk_mpf_minimum_daily_relevant_wage') * period_days
            maximum_relevant_income = self._rule_parameter('l10n_hk_mpf_maximum_daily_relevant_wage') * period_days
        return minimum_relevant_income, maximum_relevant_income

    def _get_hk_paid_amount(self, categories):
        """
        When the paid amount is very slightly off from the wage, we assume that it is due to a rounding
        error and return the wage amount instead of the computed value.
        """
        self.ensure_one()
        res = categories['BASIC']
        if float_compare(res, self._get_contract_wage(), precision_rounding=0.1) == 0:
            return self._get_contract_wage()
        return res

    def _get_previous_year_payslips(self, order=None):
        """
        Returns all payslips from the previous year, for the same struc and employee as the one being used in the payslip in
        self.
        :param order: Optional order that can be used instead of the default one when searching for the payslips.
        :return: The recordset of matching payslips from the previous year.
        """
        self.ensure_one()
        related_structs = self._get_regular_wage_structures()
        return self.env['hr.payslip'].search([
            ("state", "in", ["paid", "validated"]),
            ("date_from", ">=", self.date_from + relativedelta(months=-12, day=1)),
            ("date_to", "<", self.date_to + relativedelta(day=1)),
            ("struct_id", "in", related_structs.ids),
            ("employee_id", "=", self.employee_id.id),
        ], order=order)

    def _get_number_of_non_full_pay_days(self):
        """
        Calculates the amount of days for which the employee was not paid their full wage.
        This is important information when calculating the Average Daily Wage (ADW).
        :return: Amount of non-full pay days.
        """
        wds = self.worked_days_line_ids.filtered(lambda wd: 0 < wd.work_entry_type_id.amount_rate < 1)
        return sum([wd.number_of_days for wd in wds])

    def _get_number_of_worked_days(self, only_full_pay=False):
        """
        Calculates the amount of days during which the employee worked.
        :param only_full_pay: Optionally, filter out days were the pay was not their full wage.
        :return: Amount of worked days.
        """
        wds = self.worked_days_line_ids.filtered(lambda wd: wd.code not in ['158.00', '000.00'])
        number_of_days = sum([wd.number_of_days for wd in wds])
        if only_full_pay:
            return number_of_days - self._get_number_of_non_full_pay_days()
        return number_of_days

    def _get_credit_time_lines(self):
        if self.struct_id.country_id.code != 'HK':
            return super()._get_credit_time_lines()
        return []

    def _get_worked_day_lines_values(self, version, work_entries_vals):
        """
        Calculate the values that should be used to calculate the worked days lines of the payslip.
        Adds support for leave starting before the payslip period.
        :param domain: An optional domain used to filter work entries.
        :return: The worked days lines values.
        """
        self.ensure_one()
        if self.struct_id.country_id.code != 'HK':
            return super()._get_worked_day_lines_values(version, work_entries_vals)

        work_entries_vals = [
            vals for vals in work_entries_vals if not vals.get('leave_ids') or max(vals['leave_ids'].mapped('date_from')).date() >= self.date_from
        ]

        res = super()._get_worked_day_lines_values(version, work_entries_vals)

        hours_per_day = self._get_worked_day_lines_hours_per_day(version)
        date_from = datetime.combine(self.date_from, datetime.min.time())
        date_to = datetime.combine(self.date_to, datetime.max.time())

        work_entries_vals = self.version_id.generate_work_entries(date_from.date(), date_to.date())
        remaining_work_entries_vals = []
        for vals in work_entries_vals:
            if vals.get('leave_ids'):
                for leave in vals['leave_ids']:
                    if leave.date_from.date() < self.date_from:
                        remaining_work_entries_vals.append(vals)
                        continue

        work_entries = defaultdict(lambda: 0)
        for vals in remaining_work_entries_vals:
            for leave in vals['leave_ids']:
                work_entries[vals['work_entry_type_id'], leave] += vals['duration']

        for work_entry, hours in work_entries.items():
            work_entry_type, leave_id = work_entry
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            day_rounded = self._round_days(work_entry_type, days)
            res.append({
                'version_id': version.id,
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type.id,
                'number_of_days': day_rounded,
                'number_of_hours': hours,
                'l10n_hk_leave_id': leave_id.id,
            })
        return res

    def _get_worked_day_lines(self, versions, work_entries_vals, check_out_of_version=True):
        """
        Calculate worked days values to apply on the payslip.
        If the employee is out of contract during a part of the period, a out of contract line will be added to fill the
        gap.
        :returns: a list of dict containing the worked days values that should be applied for the given payslip
        """
        self.ensure_one()
        res = super()._get_worked_day_lines(versions, work_entries_vals, check_out_of_version)
        if self.struct_id.country_id.code != 'HK':
            return res

        sorted_versions = versions.sorted('date_version')
        for version in sorted_versions:
            if version.resource_calendar_id:
                if not check_out_of_version:
                    return res
                out_days, out_hours = 0, 0
                reference_calendar = self._get_out_of_contract_calendar(version)
                domain = Domain('work_entry_type_id.count_as', '=', 'absence')
                if (
                    version.contract_date_start
                    and self.date_from < version.contract_date_start
                    and version == sorted_versions[0]
                ):
                    start = fields.Datetime.to_datetime(self.date_from)
                    stop = fields.Datetime.to_datetime(version.contract_date_start) + relativedelta(days=-1, hour=23, minute=59)
                    out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=domain)
                    out_days += out_time['days']
                    out_hours += out_time['hours']
                if version.contract_date_end and version.contract_date_end < self.date_to and version == sorted_versions[-1]:
                    start = fields.Datetime.to_datetime(version.contract_date_end) + relativedelta(days=1)
                    stop = fields.Datetime.to_datetime(self.date_to) + relativedelta(hour=23, minute=59)
                    out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=domain)
                    out_days += out_time['days']
                    out_hours += out_time['hours']
                work_entry_type = self.env.ref('hr_work_entry.hk_hr_work_entry_type_out_of_contract', raise_if_not_found=False)
                if work_entry_type and (out_days or out_hours):
                    existing = False
                    for worked_days in res:
                        if worked_days['work_entry_type_id'] == work_entry_type.id:
                            worked_days['number_of_days'] += out_days
                            worked_days['number_of_hours'] += out_hours
                            existing = True
                            break
                    if not existing:
                        res.append({
                            'version_id': version.id,
                            'sequence': work_entry_type.sequence,
                            'work_entry_type_id': work_entry_type.id,
                            'number_of_days': out_days,
                            'number_of_hours': out_hours,
                        })
        return res

    def _get_total_non_full_pay(self):
        """ Calculate the total amount from all worked day lines concerning non-fully paid work entries. """
        total = 0
        for wd_line in self.worked_days_line_ids:
            if wd_line.work_entry_type_id.amount_rate == 1:
                continue
            total += wd_line.amount
        return total

    def _get_713_gross_at_date(self, request_date):
        """
        Helper returning the amount of the 713 gross at a specified date.
        The way it is done is by finding the last monthly payslip before that date, and getting the value from it.
        """
        employee_salary_structs = self._get_regular_wage_structures()
        latest_payslip = next(iter(self.employee_id.slip_ids.filtered(
            lambda s: s.struct_id in employee_salary_structs and s.date_to < request_date
        ).sorted()), False)
        if not latest_payslip:
            return 0.0
        return latest_payslip._get_line_values(['713_GROSS'])['713_GROSS'][latest_payslip.id]['total']

    def _get_years_of_services_per_period(self):
        """
        Calculate the years of services for the employee of the payslip, for both pre- and post-transition periods.

        :return: a tuple (pre_transition_yos, post_transition_yos)
        """
        self.ensure_one()
        contracts = self.employee_id.version_ids.sorted("contract_date_start", reverse=True)
        if not contracts:
            return 0, 0

        transition_date = date(2025, 5, 1)
        contract_end_date = contracts[0].date_end or self.date_to
        # Starts by calculating the pre-transition years of service.
        pre_transition_end_date = transition_date - relativedelta(days=1)  # April 30, 2025
        pre_transition_years = self.employee_id._get_years_of_service(self.employee_id._get_first_version_date(), pre_transition_end_date)

        # Continues by calculating the post-transition years of service.
        post_transition_start_date = transition_date
        post_transition_years = self.employee_id._get_years_of_service(max(self.employee_id._get_first_version_date(), post_transition_start_date), contract_end_date)

        return pre_transition_years, post_transition_years

    def _l10n_hk_hr_payroll_from_to_schedule(self, amount=0.0, from_schedule=None, to_schedule=None):
        """
        Helper to transform an amount from one schedule (daily, monthly, ...) to another.
        Used for scaling contractual fixed allowances (Rental, VC).
        Warning:
            Do not use for statutory MPF thresholds, which rely on exact calendar days.
        """
        if not amount:
            amount = self.version_id.wage
        if not from_schedule:
            from_schedule = self.version_id.schedule_pay
        if not to_schedule:
            to_schedule = self.version_id.schedule_pay

        if from_schedule == to_schedule:
            return amount

        # 1. Determine Working Calendar Base
        resource_calendar = self.version_id.resource_calendar_id

        if resource_calendar.hours_per_day and resource_calendar.hours_per_week:
            days_per_week = resource_calendar.hours_per_week / (resource_calendar.hours_per_day or 8.0)
        else:
            days_per_week = 5.0  # Fallback to standard 5-day week

        days_per_year = days_per_week * 52.0

        # 2. Define the Annual Multipliers
        annual_factors = {
            'daily': days_per_year,
            'weekly': 52.0,
            'bi-weekly': 26.0,
            'semi-monthly': 24.0,
            'monthly': 12.0,
        }

        # 3. Convert Source -> Annual -> Target
        from_factor = annual_factors.get(from_schedule, 12.0)
        to_factor = annual_factors.get(to_schedule, 12.0)

        annual_amount = amount * from_factor
        return annual_amount / to_factor

    def _get_daily_gross_for_period(self):
        """
        Returns the daily gross amount for the payslip period; required for MPF calculation in case of casual employees.
        We need this to be fully accurate! In order to get the correct result, we will reproduce the calculation of the
        worked day lines.
        But instead of grouping only per work entry type, we will do work entry type > day and then sum the result per
        day.
        """
        self.ensure_one()
        hours_per_day = self._get_worked_day_lines_hours_per_day(self.version_id)
        # Start by getting the work entries values for the period.
        generate_from = self.date_from + relativedelta(days=-1)
        generate_to = self.date_to + relativedelta(days=1)
        work_entries_vals = self.version_id.filtered('resource_calendar_id').generate_work_entries(generate_from, generate_to)
        # Make sure to clamp to only match work entries inside the payslip period.
        filtered_work_entries = [
            work_entry_vals for work_entry_vals in work_entries_vals if self.date_from <= work_entry_vals['date'] <= self.date_to
        ]
        # We then group the work entries by work entry type and date.
        work_entries = defaultdict(lambda: defaultdict(lambda: 0))
        for work_entry_vals in filtered_work_entries:
            work_entry_date = work_entry_vals['date']
            work_entry_type = work_entry_vals['work_entry_type_id']
            work_entries[work_entry_date][work_entry_type] += work_entry_vals['duration']
        # We want to loop on the entries day by day, and sum the amount of each day to get the daily wage.
        # In order to reuse as much logic as possible, we'll instantiate new() worked days and let their compute do the work
        # for the amount.
        gross_daily_wages = []
        for day, daily_work_entries in sorted(work_entries.items(), key=lambda x: x[0]):
            worked_day_lines = self.env['hr.payslip.worked_days']
            # We want the work entry for the day with the biggest duration to be last, so we reorder here on that level.
            work_hours_ordered = sorted(daily_work_entries.items(), key=lambda x: x[1])
            biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
            add_days_rounding = 0
            for work_entry_type, hours in work_hours_ordered:
                days = round(hours / hours_per_day, 5) if hours_per_day else 0
                if work_entry_type == biggest_work:
                    days += add_days_rounding
                day_rounded = self._round_days(work_entry_type, days)
                add_days_rounding += (days - day_rounded)
                worked_day_lines |= self.env['hr.payslip.worked_days'].new({
                    'version_id': self.version_id.id,
                    'sequence': work_entry_type.sequence,
                    'work_entry_type_id': work_entry_type.id,
                    'number_of_days': day_rounded,
                    'number_of_hours': hours,
                    'payslip_id': self.id,
                })
            gross_daily_wages.append((day, sum(worked_day_lines.mapped('amount'))))

        return gross_daily_wages

    def write(self, vals):
        """ Force the payslip to recompute itself when adding payslip inputs. """
        res = super().write(vals)
        if 'input_line_ids' in vals:
            self.filtered(lambda p: p.struct_id.country_id.code == 'HK' and p.state == 'draft').action_refresh_from_work_entries()
        return res

    # --------------
    # Action methods
    # --------------

    def action_payslip_done(self):
        """
        Force recomputation of future payslips that are potentially already created to ensure the amounts reflect
        the payslip that was just done.
        """
        res = super().action_payslip_done()
        if self.struct_id.country_id.code != 'HK':
            return res
        future_payslips = self.sudo().search([
            ('id', 'not in', self.ids),
            ('state', '=', 'draft'),
            ('employee_id', 'in', self.mapped('employee_id').ids),
            ('date_from', '>=', min(self.mapped('date_to'))),
        ])
        if future_payslips:
            future_payslips.action_refresh_from_work_entries()
        return res

    def action_payslip_cancel(self):
        """
        Allowing to cancel payslips that have been reported could lead to inconsistencies.
        Users should reset the report to draft before doing so, so that re-validation is required before submitting the
        report.
        """
        if any(report.state == 'validated' for report in self.l10n_hk_contribution_line_id.report_id):
            raise UserError(self.env._(
                "Payslips that have been included in a validated eMPF report cannot be cancelled. Please first reset the eMPF report to draft."))
        self.l10n_hk_contribution_line_id.filtered(lambda c: c.report_id.state == 'draft').unlink()
        return super().action_payslip_cancel()

    def action_payslip_draft(self):
        """
        Allowing to reset to draft payslips that have been reported could lead to inconsistencies.
        Users should reset the report to draft before doing so, so that re-validation is required before submitting the
        report.
        """
        if any(report.state == 'validated' for report in self.l10n_hk_contribution_line_id.report_id):
            raise UserError(self.env._(
                "Payslips that have been included in a validated eMPF report cannot be reset to draft. Please first reset the eMPF report to draft."))
        self.l10n_hk_contribution_line_id.filtered(lambda c: c.report_id.state == 'draft').unlink()
        return super().action_payslip_draft()

    def action_payslip_payment_report(self, export_format='l10n_hk_mri'):
        action = super().action_payslip_payment_report()
        if self.company_id.country_code != 'HK':
            return action
        action.update({
            'context': {
                **action['context'],
                'default_export_format': export_format,
            },
        })
        return action

    @api.model
    def _issues_dependencies(self):
        issue_defs = super()._issues_dependencies()
        issue_defs.append('l10n_hk_rental_id')
        return issue_defs

    def compute_sheet(self):
        """
        The rental assigned to a payslip should be recomputed with the sheet to stay up to date.
        We pick up the rental based on the payslip details and the related employee's rental status
        at the time of generating the payslip's lines.
        """
        employees_rentals = self.env["l10n_hk.rental"]._read_group(
            domain=[("employee_id", "in", self.employee_id.ids), ('state', '=', 'confirmed')],
            groupby=["employee_id"],
            aggregates=['id:recordset'],
        )
        employees_rentals = dict(employees_rentals or {})
        for payslip in self:
            if payslip.state != 'draft':
                continue

            employee_rentals = employees_rentals.get(payslip.employee_id)
            # Sometimes we have more than one active rental, but they will never be for the same
            # Period. So we simply need to filter based on the date to pick the rental relevant to
            # this payslip.
            employee_rentals = employee_rentals and employee_rentals.filtered(
                lambda r: (not r.date_end or r.date_end >= payslip.date_from) and r.date_start <= payslip.date_to
            )
            payslip.l10n_hk_rental_id = employee_rentals and next(iter(employee_rentals))

        return super().compute_sheet()
