# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import UTC, datetime, time

from dateutil.relativedelta import relativedelta
from odoo.tools import float_round

from odoo import api, fields, models

UZ_STATUTORY_WORKING_DAYS = 25.3


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    l10n_uz_average_monthly_wage = fields.Float(
            string="Uzbekistan Average Monthly Wage",
            compute="_compute_l10n_uz_average_monthly_wage",
            help="Average monthly wage based on the worked days and income for the employee in the last 12 calendar months."
        )
    l10n_uz_average_daily_wage = fields.Float(
            string="Uzbekistan Average Daily Wage",
            compute="_compute_l10n_uz_average_daily_wage",
            help="Average daily wage based on the worked days and income for the employee in the last 12 calendar months."
        )

    def _l10n_uz_is_departure_payslip(self):
        """
        Determines if the current payslip is a departure payslip for the employee.
        Departure reason and date is required since the severance payment depends on them.
        """
        self.ensure_one()
        return bool(
            self.employee_id.departure_date
            and self.employee_id.departure_reason_id
            and self.date_from <= self.employee_id.departure_date <= self.date_to
        )

    def _l10n_uz_get_ytd_payslips(self):
        """
        Returns the validated/paid payslips for the employee in the last 12 calendar months or since the start of
        employment if employed for less than 12 months for YTD calculations.
        Article 257: https://lex.uz/en/docs/6257291
        """
        self.ensure_one()

        contract_start_date = self.employee_id.first_contract_date or self.version_id.date_start or self.date_from
        ytd_year_start_date = max(self.date_to + relativedelta(months=-12, day=1), contract_start_date + relativedelta(day=1))
        ytd_year_end_date = self.date_to + relativedelta(months=-1, day=31)

        ytd_payslips = self.env["hr.payslip"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "in", ["validated", "paid"]),
            ("date_from", ">=", ytd_year_start_date),
            ("date_to", "<=", ytd_year_end_date),
        ], order="date_from")
        return ytd_payslips

    @api.depends('employee_id', 'date_to', 'date_from', 'version_id.l10n_uz_initial_average_monthly_wage')
    def _compute_l10n_uz_average_daily_wage(self):
        """
        The average wage for the employee is computed by summing all payments made to the employee during the past
        12 months (or the start of employment if contract started less than 12 months ago), including the base salary
        and bonuses and allowances, divided by the number of full months worked.
        In the computation, only the remunerations and time actually worked by the employee is used.
        For months that are partially worked due to employee absence for reasons listed in Article 257 of the Labor Code,
        the number of worked days is computed as follows:
            effective_worked_days = (25.3 / num_scheduled_working_days) * num_actual_worked_days
            avg_daily_wage = (base_salary + allowances - remun_during_absence) / effective_worked_days

        The initial average monthly wage is used in computations for missing months within the 12-month period.

        Article 257: https://lex.uz/en/docs/6257288
        """
        self.l10n_uz_average_daily_wage = 0.0
        uz_payslips = self.filtered(lambda p: p.company_id.country_id.code == 'UZ' and p.employee_id and p.date_to)
        if not uz_payslips:
            return

        min_start_date = min(
            max(p.date_to + relativedelta(months=-12, day=1), (p.employee_id.first_contract_date or p.version_id.date_start or p.date_from) + relativedelta(day=1))
            for p in uz_payslips
        )
        max_end_date = max(p.date_to + relativedelta(months=-1, day=31) for p in uz_payslips)
        employee_ids = uz_payslips.employee_id.ids

        all_ytd_payslips = self.env["hr.payslip"].search([
            ("employee_id", "in", employee_ids),
            ("state", "in", ["validated", "paid"]),
            ("date_from", ">=", min_start_date),
            ("date_to", "<=", max_end_date),
        ], order="date_from")

        ytd_by_employee = all_ytd_payslips.grouped('employee_id')

        target_structures = uz_payslips.struct_id
        gross_rules = target_structures.rule_ids.filtered(
            lambda rule: any(category.code == 'GROSS' for category in rule.category_ids)
        )
        gross_rule_codes = list(set(gross_rules.mapped('code')))
        gross_line_values = all_ytd_payslips._get_line_values(gross_rule_codes) if all_ytd_payslips and gross_rule_codes else {}
        ytd_by_employee = all_ytd_payslips.grouped('employee_id')

        for payslip in uz_payslips:
            contract_start_date = payslip.employee_id.first_contract_date or payslip.version_id.date_start or payslip.date_from
            ytd_year_start_date = max(payslip.date_to + relativedelta(months=-12, day=1), contract_start_date + relativedelta(day=1))
            ytd_year_end_date = payslip.date_to + relativedelta(months=-1, day=31)

            emp_slips = ytd_by_employee.get(payslip.employee_id, self.env['hr.payslip'])
            ytd_payslips = emp_slips.filtered(lambda s: ytd_year_start_date <= s.date_from and s.date_to <= ytd_year_end_date)

            ytd_worked_days = 0.0
            ytd_total_paid_amount = 0.0

            for ytd_slip in ytd_payslips:
                calendar = ytd_slip.version_id.resource_calendar_id
                scheduled_working_days = calendar.get_work_duration_data(
                    datetime.combine(ytd_slip.date_from, time.min).replace(tzinfo=UTC),
                    datetime.combine(ytd_slip.date_to, time.max).replace(tzinfo=UTC),
                    compute_leaves=False,
                )['days']

                if not scheduled_working_days:
                    continue

                absent_amount = 0.0
                worked_days = 0.0

                for wd in ytd_slip.worked_days_line_ids:
                    if wd.work_entry_type_id.count_as == 'working_time':
                        worked_days += wd.number_of_days
                    elif wd.work_entry_type_id.count_as == 'absence':
                        absent_amount += wd.amount

                ytd_worked_days += (UZ_STATUTORY_WORKING_DAYS / scheduled_working_days) * worked_days

                slip_gross_paid = sum(
                    gross_line_values[code][ytd_slip.id]['total']
                    for code in gross_rule_codes
                )
                ytd_total_paid_amount += (slip_gross_paid - absent_amount)

            # Process historical months prior to available YTD payslips
            # The initial average wage is used for all the missing historical months prior to available payslips
            ytd_gap_start_date = max(payslip.date_from + relativedelta(months=-12, day=1), contract_start_date)
            ytd_gap_end_date = payslip.date_from + relativedelta(days=-1)

            if ytd_gap_start_date <= ytd_gap_end_date:
                gap_end_date = ytd_payslips[0].date_from if ytd_payslips else payslip.date_from
                delta = relativedelta(gap_end_date.replace(day=1), ytd_gap_start_date.replace(day=1))
                missing_months = (delta.years * 12) + delta.months
            else:
                missing_months = 1

            initial_monthly = payslip.version_id.l10n_uz_initial_average_monthly_wage or payslip.version_id.wage or 0.0
            ytd_total_paid_amount += initial_monthly * missing_months
            ytd_worked_days += UZ_STATUTORY_WORKING_DAYS * missing_months

            payslip.l10n_uz_average_daily_wage = (ytd_total_paid_amount / ytd_worked_days) if ytd_worked_days else 0.0

    @api.depends('l10n_uz_average_daily_wage')
    def _compute_l10n_uz_average_monthly_wage(self):
        """
        The average monthly wage is computed as the average daily wage multiplied by the average number of working days in a month
        (25.3 days is the standard in Uzbekistan due to assuming a 6-day work week.
        """
        for payslip in self:
            payslip.l10n_uz_average_monthly_wage = payslip.l10n_uz_average_daily_wage * UZ_STATUTORY_WORKING_DAYS

    def _l10n_uz_severance_payment_amount(self):
        """
        Severance base amount is based on the average monthly wage from the last 12 months.
        Severance pay multiplier based on years of service.
        Returns 0.0 if the departure reason does not entitle the employee to severance pay.
        Article 173: https://lex.uz/en/docs/6257291
        """
        self.ensure_one()
        reason = self.employee_id.departure_reason_id
        if not reason.l10n_uz_is_severance_paid:
            return 0.0

        start_date = self.employee_id.first_contract_date
        end_date = self.employee_id.departure_date

        years_of_service = relativedelta(end_date, start_date).years

        severance_rates = self.env['hr.rule.parameter']._get_parameter_from_code("l10n_uz_severance_rates", self.date_to) or []

        for rate_info in severance_rates:
            threshold = rate_info['years_of_service_threshold']
            if years_of_service < threshold:
                return rate_info['percentage']
        return 0.0

    def _l10n_uz_remaining_leave_days_for_compensation(self):
        """
        Remaining annual leave days owed to the employee on departure.

        Earned = round(eligible_days / 12 * months_in_current_work_year)
          - Months with >= 15 days count as a full month; < 15 days count as 0.
          - Rounding is half-up (0.5 to 1).
        Taken = calendar days of validated annual leave in the current work year.
        Returns max(Earned - Taken, 0).
        Article 223-225: https://lex.uz/en/docs/6257291#6263015
        """
        self.ensure_one()

        if not self.employee_id.first_contract_date:
            return 0.0
        last_anniversary = self.employee_id.first_contract_date + relativedelta(year=self.date_to.year)
        if last_anniversary > self.date_to:
            last_anniversary -= relativedelta(years=1)

        time_since_last_anniversary = relativedelta(self.date_to, last_anniversary)
        months_since_anniversary = time_since_last_anniversary.years * 12 + time_since_last_anniversary.months + (1 if time_since_last_anniversary.days >= 15 else 0)

        # Earned leaves
        eligible_leaves = self.version_id.l10n_uz_annual_leave_eligibility or 21.0
        earned_amount = float_round((eligible_leaves / 12.0) * months_since_anniversary, precision_digits=0, rounding_method="HALF-UP")

        # Taken leaves
        annual_leave_type = self.employee_id.company_id.l10n_uz_annual_leave_work_entry_type_id
        taken_amount = 0.0
        if annual_leave_type:
            taken_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', self.employee_id.id),
                ('work_entry_type_id', '=', annual_leave_type.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', self.date_to),
                ('date_to', '>=', last_anniversary),
            ])
            taken_amount = sum(taken_leaves.mapped('number_of_days'))

        # Remaining days
        remaining_days = max(0.0, earned_amount - taken_amount)
        return remaining_days

    def _l10n_uz_get_annual_leave_provision(self):
        """
        Computation for the annual leave provision. Does not contribute to the employee or employer
        payments.
        """
        self.ensure_one()
        return (self.version_id.l10n_uz_annual_leave_eligibility / 12.0) * self.l10n_uz_average_daily_wage

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_uz_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_rule_parameter_data.xml',
                'data/hr_salary_rule_data.xml',
            ])]
