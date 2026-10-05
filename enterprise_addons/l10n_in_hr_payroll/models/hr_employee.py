# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import date_utils, float_round, format_amount


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_in_uan = fields.Char(string='UAN', groups="hr.group_hr_user", copy=False)
    l10n_in_pan = fields.Char(string='PAN', groups="hr.group_hr_user", copy=False)
    l10n_in_esic_number = fields.Char(string='ESIC Number', groups="hr.group_hr_user", copy=False)
    l10n_in_lwf_account_number = fields.Char("LWF Account Number", groups="hr.group_hr_user", tracking=True)
    l10n_in_medical_insurance = fields.Monetary(readonly=False, related="version_id.l10n_in_medical_insurance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_insured_spouse = fields.Boolean(readonly=False, related="version_id.l10n_in_insured_spouse", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_insured_first_children = fields.Boolean(readonly=False, related="version_id.l10n_in_insured_first_children", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_insured_second_children = fields.Boolean(readonly=False, related="version_id.l10n_in_insured_second_children", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_medical_insurance_total = fields.Monetary(readonly=False, related="version_id.l10n_in_medical_insurance_total", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_provident_fund = fields.Boolean(readonly=False, related="version_id.l10n_in_provident_fund", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_enabled = fields.Boolean(readonly=False, related="version_id.l10n_in_pf_enabled", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employer_type = fields.Selection(readonly=False, related="version_id.l10n_in_pf_employer_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employee_type = fields.Selection(readonly=False, related="version_id.l10n_in_pf_employee_type", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employee_amount = fields.Monetary(readonly=False, related="version_id.l10n_in_pf_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employer_amount = fields.Monetary(readonly=False, related="version_id.l10n_in_pf_employer_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employee_percentage = fields.Float(readonly=False, related="version_id.l10n_in_pf_employee_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_employer_percentage = fields.Float(readonly=False, related="version_id.l10n_in_pf_employer_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_hra = fields.Monetary(readonly=False, related="version_id.l10n_in_hra", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_hra_percentage = fields.Float(readonly=False, related="version_id.l10n_in_hra_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_fixed_allowance = fields.Monetary(readonly=False, related="version_id.l10n_in_fixed_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_fixed_allowance_percentage = fields.Float(readonly=False, related="version_id.l10n_in_fixed_allowance_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_gratuity = fields.Monetary(readonly=False, related="version_id.l10n_in_gratuity", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_gratuity_percentage = fields.Float(readonly=False, related="version_id.l10n_in_gratuity_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic_employee_percentage = fields.Float(readonly=False, related="version_id.l10n_in_esic_employee_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic_employee_amount = fields.Monetary(readonly=False, related="version_id.l10n_in_esic_employee_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic_employer_amount = fields.Monetary(readonly=False, related="version_id.l10n_in_esic_employer_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_esic_employer_percentage = fields.Float(readonly=False, related="version_id.l10n_in_esic_employer_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_residing_child_hostel = fields.Integer(readonly=False, related="version_id.l10n_in_residing_child_hostel", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_performance_bonus = fields.Monetary(readonly=False, related="version_id.l10n_in_performance_bonus", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_performance_bonus_percentage = fields.Float(readonly=False, related="version_id.l10n_in_performance_bonus_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_leave_travel_percentage = fields.Float(readonly=False, related="version_id.l10n_in_leave_travel_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_leave_travel_allowance = fields.Monetary(readonly=False, related="version_id.l10n_in_leave_travel_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_standard_allowance = fields.Monetary(readonly=False, related="version_id.l10n_in_standard_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_standard_allowance_percentage = fields.Float(readonly=False, related="version_id.l10n_in_standard_allowance_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_basic_percentage = fields.Float(readonly=False, related="version_id.l10n_in_basic_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_basic_salary_amount = fields.Monetary(readonly=False, related="version_id.l10n_in_basic_salary_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_phone_subscription = fields.Monetary(readonly=False, related="version_id.l10n_in_phone_subscription", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_internet_subscription = fields.Monetary(readonly=False, related="version_id.l10n_in_internet_subscription", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_meal_voucher_amount = fields.Monetary(readonly=False, related="version_id.l10n_in_meal_voucher_amount", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_company_transport = fields.Monetary(readonly=False, related="version_id.l10n_in_company_transport", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_income_from_other_sources = fields.Monetary(readonly=False, related="version_id.l10n_in_income_from_other_sources", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_income_let_out_property = fields.Monetary(readonly=False, related="version_id.l10n_in_income_let_out_property", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_interest_fd_deposit = fields.Monetary(readonly=False, related="version_id.l10n_in_interest_fd_deposit", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_interest_national_savings = fields.Monetary(readonly=False, related="version_id.l10n_in_interest_national_savings", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_conveyance_allowance = fields.Monetary(readonly=False, related="version_id.l10n_in_conveyance_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_contribution_nps = fields.Monetary(readonly=False, related="version_id.l10n_in_contribution_nps", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_income_previous_employment = fields.Monetary(readonly=False, related="version_id.l10n_in_income_previous_employment", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_tax_paid_previous_employer = fields.Monetary(readonly=False, related="version_id.l10n_in_tax_paid_previous_employer", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    pt_rule_parameter_id = fields.Many2one(readonly=False, related="version_id.pt_rule_parameter_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_professional_tax_deduction_cycle = fields.Selection(readonly=False, related="version_id.l10n_in_professional_tax_deduction_cycle", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_lwf_employer_contribution = fields.Monetary(readonly=False, related="version_id.l10n_in_lwf_employer_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_lwf_employee_contribution = fields.Monetary(readonly=False, related="version_id.l10n_in_lwf_employee_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_lwf_deduction_cycle = fields.Selection(readonly=False, related="version_id.l10n_in_lwf_deduction_cycle", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_tds_deduction_cycle = fields.Selection(readonly=False, related="version_id.l10n_in_tds_deduction_cycle", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_in_pf_account_number = fields.Char("PF Account Number", groups="hr.group_hr_user")

    _unique_l10n_in_uan = models.Constraint(
        'unique (l10n_in_uan)',
        "This UAN already exists",
    )
    _unique_l10n_in_pan = models.Constraint(
        'unique (l10n_in_pan)',
        "This PAN already exists",
    )
    _unique_l10n_in_esic_number = models.Constraint(
        'unique (l10n_in_esic_number)',
        "This ESIC Number already exists",
    )

    def _get_employees_with_invalid_ifsc(self):
        invalid_in_bank_acc_ids = self.bank_account_ids.filtered(
            lambda bank_acc: bank_acc.country_code == "IN"
        )._l10n_in_get_invalid_ifsc_accounts()
        return self.filtered(lambda employee: not employee.bank_account_ids or employee.bank_account_ids & invalid_in_bank_acc_ids)

    @api.model
    def notify_expiring_contract_work_permit(self):
        employee_type_id = self.env.ref('l10n_in_hr_payroll.l10n_in_contract_type_probation', raise_if_not_found=False)
        if employee_type_id:
            one_week_ago = fields.Date.today() - timedelta(weeks=1)
            versions = self.env['hr.version'].search([
                ('contract_date_end', '=', one_week_ago), ('employee_type_id', '=', employee_type_id.id)
            ])
            for version in versions:
                version.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=version.hr_responsible_id.id,
                    note=_("End date of %(name)s's contract is today.", name=version.employee_id.name),
                )
        return super().notify_expiring_contract_work_permit()

    def _get_address_lines(self):
        self.ensure_one()
        return [
            self.private_street or 'NA',
            self.private_street2 or '',
            self.private_city or '',
            self.private_state_id.name if self.private_state_id else '',
            self.private_country_id.name if self.private_country_id else '',
        ]

    def _get_tds_q4_category(self, fy_date_end):
        self.ensure_one()
        if age := self._get_age(fy_date_end):
            if age >= 80:
                return 'O'
            if age >= 60:
                return 'S'
        return 'W' if self.sex == 'female' else 'G'

    # ------------------------------------------------------------------
    # Indian Payroll: TDS computation helpers
    # ------------------------------------------------------------------

    def _l10n_in_get_tds_deduction_months(self, schedule):
        return {
            'quarterly': {3, 6, 9, 12},
            'half_yearly': {3, 9},
            'last_three_months': {1, 2, 3},
        }.get(schedule)

    def _l10n_in_count_remaining_deductions(self, schedule, tds_reference_start, fy_end_date):
        deduction_months = self._l10n_in_get_tds_deduction_months(schedule)
        count = 0
        current = tds_reference_start.replace(day=1)
        fy_end_month_start = fy_end_date.replace(day=1)
        while current <= fy_end_month_start:
            if current.month in deduction_months:
                count += 1
            current += relativedelta(months=1)
        return max(count, 1)

    def _l10n_in_get_remaining_fy_months(self, tds_reference_start, fy_end_date):
        fy_end_month_start = fy_end_date.replace(day=1)
        if tds_reference_start > fy_end_month_start:
            fy_end_month_start += relativedelta(years=1)
        return max(relativedelta(fy_end_month_start, tds_reference_start).months + 1, 1)

    def _l10n_in_get_next_tds_deduction_start(self, schedule, tds_reference_start, fy_end_date):
        deduction_months = self._l10n_in_get_tds_deduction_months(schedule)
        current = tds_reference_start.replace(day=1)
        fy_end_month_start = fy_end_date.replace(day=1)
        while current <= fy_end_month_start:
            if current.month in deduction_months:
                break
            current += relativedelta(months=1)
        return current

    def _l10n_in_get_tds_expected_amount(self, schedule, tds_reference_start, fy_end_date, remaining_tds):
        next_deduction_start = self._l10n_in_get_next_tds_deduction_start(
            schedule, tds_reference_start, fy_end_date)
        deductions_left = self._l10n_in_count_remaining_deductions(
            schedule, next_deduction_start, fy_end_date)
        return float_round(remaining_tds / deductions_left, precision_digits=2)

    def _l10n_in_get_financial_year_bounds(self, financial_year=None, reference_date=None):
        """Return the financial year start and end dates for the given reference date."""
        reference_date = reference_date or fields.Date.context_today(self)

        if financial_year:
            try:
                start_year = int(str(financial_year).split('-')[0])
            except (ValueError, IndexError):
                start_year = reference_date.year if reference_date.month >= 4 else reference_date.year - 1
        else:
            start_year = reference_date.year if reference_date.month >= 4 else reference_date.year - 1

        end_year = start_year + 1
        date_start = fields.Date.from_string(f"{start_year}-04-01")
        date_end = fields.Date.from_string(f"{end_year}-03-31")
        return date_start, date_end

    def _l10n_in_get_financial_year_selection(self):
        today = fields.Date.context_today(self)
        fiscal_start, fiscal_end = date_utils.get_fiscal_year(today, 31, 3)

        def format_range(start_date, end_date):
            start_year = start_date.year
            end_year = end_date.year
            return (
                f"{start_year}-{end_year}",
                f"{start_year}-{end_date.strftime('%y')}",
            )

        return [
            format_range(
                fiscal_start - relativedelta(years=year),
                fiscal_end - relativedelta(years=year),
            )
            for year in range(5)
        ]

    def _l10n_in_get_tax_input_values(self, version=None, date=None):
        version = version or self.current_version_id
        let_out_property_std_deduction = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'l10n_in_house_property_std_deduction', date=date
        )
        return {
            'income_from_other_sources': version.l10n_in_income_from_other_sources,
            'income_let_out_property': version.l10n_in_income_let_out_property * (1 - let_out_property_std_deduction),
            'interest_fd_deposit': version.l10n_in_interest_fd_deposit,
            'interest_national_savings': version.l10n_in_interest_national_savings,
            'conveyance_allowance': version.l10n_in_conveyance_allowance,
            'contribution_nps': version.l10n_in_contribution_nps,
            'income_previous_employment': version.l10n_in_income_previous_employment,
            'tax_paid_previous_employer': version.l10n_in_tax_paid_previous_employer,
        }

    def _l10n_in_collect_tax_payslips(self, date_start, date_end, exclude_payslip_ids=None):
        domain = [
            ('employee_id', '=', self.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_start),
            ('date_to', '<=', date_end),
        ]
        if exclude_payslip_ids:
            domain.append(('id', 'not in', list(exclude_payslip_ids)))
        return dict(self.env['hr.payslip'].sudo()._read_group(domain, ['version_id'], ['id:recordset']))

    def _l10n_in_get_grouped_payslips(self, payslips_by_version, versions=None):
        grouped_payslips = self.env['hr.payslip']
        if versions:
            for version_id in versions:
                grouped_payslips |= payslips_by_version.get(version_id, self.env['hr.payslip'])
        else:
            for payslips in payslips_by_version.values():
                grouped_payslips |= payslips
        return grouped_payslips

    def _l10n_in_calculate_tax_breakup(self, taxable_income, tax_slabs):
        """Return the detailed tax breakup for the provided taxable income."""
        tax_breakup = []
        total_tax_amount = 0.0
        for rate, (lower_limit, upper_limit) in tax_slabs:
            if taxable_income <= lower_limit:
                break
            taxable_amount = min(taxable_income, float(upper_limit)) - lower_limit
            tax_per_slab = round(taxable_amount * rate)
            total_tax_amount += tax_per_slab
            tax_breakup.append({
                'id': len(tax_breakup) + 1,
                'lower_limit': lower_limit,
                'upper_limit': upper_limit,
                'tax_rate': rate * 100,
                'tax_amount': tax_per_slab,
            })
        return tax_breakup, total_tax_amount

    def _l10n_in_get_tax_parameters(self, reference_date):
        rule_parameter = self.env['hr.rule.parameter'].sudo()

        return {
            'tax_slabs': rule_parameter._get_parameter_from_code(
                'l10n_in_tds_rate_chart',
                date=reference_date,
            ),
            'surcharge_slabs': rule_parameter._get_parameter_from_code(
                'l10n_in_surcharge_rate',
                date=reference_date,
            ),
            'min_income_surcharge': rule_parameter._get_parameter_from_code(
                'l10n_in_min_income_surcharge',
                date=reference_date,
            ),
            'min_income_rebate': rule_parameter._get_parameter_from_code(
                'l10n_in_min_income_tax_rebate',
                date=reference_date,
            ),
            'max_tax_slabs': rule_parameter._get_parameter_from_code(
                'l10n_in_max_surcharge_tax_rate',
                date=reference_date,
            ),
            'cess_percentage': rule_parameter._get_parameter_from_code(
                'l10n_in_cess_percentage',
                date=reference_date,
            ),
        }

    def _l10n_in_get_tax_totals(self, taxable_income, tax_parameters):
        tax_breakup, tax_on_taxable_income = self._l10n_in_calculate_tax_breakup(taxable_income, tax_parameters['tax_slabs'])

        if taxable_income >= tax_parameters['min_income_rebate']:
            marginal_income = taxable_income - tax_parameters['min_income_rebate']
            rebate = max(tax_on_taxable_income - marginal_income, 0.0)
        else:
            rebate = tax_on_taxable_income
        total_tax_on_income = tax_on_taxable_income - rebate

        surcharge = 0.0

        if taxable_income > tax_parameters['min_income_surcharge']:
            for rate, amount in tax_parameters['surcharge_slabs']:
                if taxable_income <= float(amount[1]):
                    surcharge = round(total_tax_on_income * rate)
                    break

            max_taxable_income = 0
            max_tax = 0
            max_surcharge = 0

            for income, tax, surcharge_rate in tax_parameters['max_tax_slabs']:
                if taxable_income <= income:
                    break
                max_taxable_income = income
                max_tax = tax
                max_surcharge = surcharge_rate

            excess_income = taxable_income - max_taxable_income
            max_tax_with_surcharge = max_tax + max_surcharge
            total_tax_with_surcharge = total_tax_on_income + surcharge
            excess_tax = total_tax_with_surcharge - max_tax_with_surcharge

            if excess_tax > excess_income:
                surcharge = max_tax_with_surcharge + excess_income - total_tax_on_income

        cess = round((total_tax_on_income + surcharge) * tax_parameters['cess_percentage'])
        total_tds_tobe_paid = total_tax_on_income + surcharge + cess

        return {
            'tax_breakup': tax_breakup,
            'tax_on_taxable_income': tax_on_taxable_income,
            'rebate': rebate,
            'total_tax_on_income': total_tax_on_income,
            'surcharge': surcharge,
            'cess': cess,
            'total_tds_tobe_paid': total_tds_tobe_paid,
            'net_tax_payable': total_tds_tobe_paid,
        }

    def _l10n_in_get_tds_total(self, payslips):
        if not payslips:
            return 0.0
        line_values = payslips._get_line_values(['TDS'], ['total'], compute_sum=True)
        return line_values.get('TDS', {}).get('sum', {}).get('total', 0.0)

    def _l10n_in_format_amount(self, amount, currency):
        """Format amount for display using Odoo formatter."""
        if isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                return amount
        if isinstance(amount, float):
            if math.isinf(amount):
                return self.env._("Infinity")
            if math.isnan(amount):
                return "0.0"
        return format_amount(self.env, amount or 0.0, currency)

    def _l10n_in_get_tds_reference_start(self, date_start, current_version_payslips):
        """Return the month start date from which to spread the remaining TDS."""
        start_month = date_start.replace(day=1)
        if current_version_payslips:
            last_month_start = max(current_version_payslips.mapped('date_from')).replace(day=1)
            start_month = max(start_month, last_month_start + relativedelta(months=1))
        return start_month

    def _l10n_in_get_employee_yearly_net_amount(self, date_start, employee_version, payslips):
        """Estimate FY net income (excluding TDS) using actual payslips + projected months.

        :param date_start: Financial year start boundary.
        :param employee_version: Version used to simulate missing months.
        :param payslips: Payslips already generated within the financial year (sorted later).
        :return: Net income (excluding TDS) projected for the whole financial year.
        """
        def _remaining_months_until_fy_end(month_start_date, fy_end_month=3):
            if month_start_date.month == fy_end_month:
                return 1
            return ((fy_end_month - month_start_date.month) % 12) + 1

        def _clamp_to_contract(month_start_date):
            clamped_month_start = max(filter(None, [month_start_date, contract_start]))
            if contract_end and clamped_month_start > contract_end:
                clamped_month_start = contract_end.replace(day=1)
            return clamped_month_start

        def _simulate_projected_gross(version_record, month_start_date, projection_start_month):
            Payslip = self.env['hr.payslip']
            with self.env.cr.savepoint() as savepoint:
                simulation = Payslip.sudo().create({
                    'name': 'Payslip Simulation',
                    'employee_id': version_record.employee_id.id,
                    'version_id': version_record.id,
                    'date_from': month_start_date,
                    'date_to': month_start_date + relativedelta(months=1, days=-1),
                    'struct_id': version_record.structure_type_id.default_struct_id.id,
                    'company_id': version_record.employee_id.company_id.id,
                })
                simulation.with_context(calculate_tds=False).compute_sheet()
                simulation.action_payslip_draft()
                monthly_gross, _tds_total = Payslip._l10n_in_taxable_gross_total([(self, simulation)]).get(self.id, (0.0, 0.0))
                savepoint.rollback()
                return float_round(
                    monthly_gross * _remaining_months_until_fy_end(projection_start_month),
                    precision_digits=2,
                )

        contract_start = employee_version.contract_date_start
        contract_end = employee_version.contract_date_end

        period_start = max(filter(None, [contract_start, date_start]))
        if period_start.day != 1:
            period_start = period_start.replace(day=1)

        # no actual payslips -> simulate from contract start and project from period_start
        if not payslips:
            reference_month_start = _clamp_to_contract(period_start)
            return _simulate_projected_gross(employee_version, reference_month_start, period_start)
        yearly_gross_total, _tds_total = self.env['hr.payslip']._l10n_in_taxable_gross_total([(self, payslips)]).get(self.id, (0.0, 0.0))
        latest_payslip = payslips[-1]

        # last payslip belongs to past version, but target version is current
        if not latest_payslip.version_id.is_current and employee_version.is_current:
            reference_month_start = _clamp_to_contract(period_start)
            projection_start_month = reference_month_start
        else:
            if latest_payslip.date_from.month == 3:
                return yearly_gross_total

            reference_month_start = max(latest_payslip.date_from, period_start + relativedelta(months=-1))
            reference_month_start = _clamp_to_contract(reference_month_start)

            projection_start_month = reference_month_start
            if latest_payslip.version_id == employee_version:
                projection_start_month += relativedelta(months=1)

        yearly_gross_total += _simulate_projected_gross(
            employee_version, reference_month_start, projection_start_month,
        )

        return yearly_gross_total

    def _l10n_in_prepare_tax_declaration_values(self, date_start, date_end,
        employee_version, payslips, current_version_payslips, tds_only=False):
        """Compute tax figures for a given version and financial year.

        :param financial_year: Label of the year (e.g., "2024-2025").
        :param date_start: Effective start date for the computation window.
        :param date_end: Financial year end date.
        :param employee_version: Version to compute on.
        :param payslips: All payslips in the window for this employee.
        :param current_version_payslips: Payslips of the current version to deduct already paid TDS.
        :param tax_inputs: Extra income/deductions dict from `_l10n_in_get_tax_input_values`.
        :param tds_only: When True, return only the scheduled TDS amount to deduct.
        :return: Scheduled TDS (float) when `tds_only` else full declaration dict with raw and formatted values.
        """
        rule_parameter = self.env['hr.rule.parameter'].sudo()
        standard_deduction = rule_parameter._get_parameter_from_code('l10n_in_standard_deduction', date=date_start)
        payslips = payslips.sorted(lambda slip: slip.date_from)
        total_income = self._l10n_in_get_employee_yearly_net_amount(date_start, employee_version, payslips)
        tax_inputs = self._l10n_in_get_tax_input_values(employee_version, date=date_start)
        final_income = total_income + (
            tax_inputs['income_from_other_sources'] +
            tax_inputs['income_let_out_property'] +
            tax_inputs['interest_fd_deposit'] +
            tax_inputs['interest_national_savings'] +
            tax_inputs['income_previous_employment']
        )
        total_exemption = standard_deduction + tax_inputs['conveyance_allowance'] + tax_inputs['contribution_nps']
        taxable_income = max(final_income - total_exemption, 0.0)
        tax_parameters = self._l10n_in_get_tax_parameters(date_start)
        tax_totals = self._l10n_in_get_tax_totals(taxable_income, tax_parameters)
        tax_breakup = tax_totals['tax_breakup']
        tax_on_taxable_income = tax_totals['tax_on_taxable_income']
        rebate = tax_totals['rebate']
        total_tax_on_income = tax_totals['total_tax_on_income']
        surcharge = tax_totals['surcharge']
        cess = tax_totals['cess']
        total_tds_tobe_paid = tax_totals['total_tds_tobe_paid']
        already_paid_tds = -self._l10n_in_get_tds_total(payslips) + tax_inputs['tax_paid_previous_employer']
        remaining_tds = max(total_tds_tobe_paid - already_paid_tds, 0.0)
        tds_reference_start = self._l10n_in_get_tds_reference_start(date_start, current_version_payslips)

        schedule = employee_version.l10n_in_tds_deduction_cycle
        if schedule and schedule != 'monthly':
            expected_tds = self._l10n_in_get_tds_expected_amount(schedule, tds_reference_start, date_end, remaining_tds)
        else:
            months_left = self._l10n_in_get_remaining_fy_months(tds_reference_start, date_end)
            expected_tds = float_round(remaining_tds / months_left, precision_digits=2)

        if tds_only:
            return expected_tds

        currency = employee_version.employee_id.company_id.currency_id or self.env.company.currency_id
        amount_values = {
            'total_income': total_income,
            'final_income': final_income,
            'standard_deduction': -standard_deduction,
            'total_exemption': -total_exemption,
            'taxable_income': taxable_income,
            'tax_on_taxable_income': tax_on_taxable_income,
            'rebate': rebate,
            'total_tax_on_income': total_tax_on_income,
            'surcharge': surcharge,
            'cess': cess,
            'total_tds_tobe_paid': total_tds_tobe_paid,
            'already_paid_tds': already_paid_tds,
            'current_version_paid_tds': -self._l10n_in_get_tds_total(current_version_payslips),
            'remaining_tds': remaining_tds,
            'expected_tds': expected_tds,
            'tax_breakup_total': tax_on_taxable_income,
            **{
                key: tax_inputs[key]
                for key in [
                    'income_previous_employment',
                    'income_from_other_sources',
                    'income_let_out_property',
                    'interest_fd_deposit',
                    'interest_national_savings',
                    'conveyance_allowance',
                    'contribution_nps',
                    'tax_paid_previous_employer',
                ]
            },
        }
        formatted_values = {
            key: self._l10n_in_format_amount(value, currency)
            for key, value in amount_values.items()
        }
        formatted_values['tax_breakup'] = [{
            'id': entry.get('id'),
            'tax_rate': entry.get('tax_rate'),
            'lower_limit': self._l10n_in_format_amount(entry.get('lower_limit'), currency),
            'upper_limit': self._l10n_in_format_amount(entry.get('upper_limit'), currency),
            'tax_amount': self._l10n_in_format_amount(entry.get('tax_amount'), currency),
        } for entry in tax_breakup]
        schedule_label = dict(self._fields['l10n_in_tds_deduction_cycle']._description_selection(self.env))
        return {
            **amount_values,
            'display_name': employee_version.display_name,
            'version_id': employee_version,
            'contract_date_start': employee_version.contract_date_start.strftime('%d/%m/%Y'),
            'contract_date_end': employee_version.contract_date_end.strftime('%d/%m/%Y') if employee_version.contract_date_end else None,
            'schedule_label': schedule_label.get(employee_version.l10n_in_tds_deduction_cycle, 'Monthly'),
            'formatted_values': formatted_values,
        }

    def l10n_in_compute_tax_declaration(self, version, exclude_payslip_ids, start_date):
        """Compute the scheduled TDS to deduct for the employee's Indian payroll.

        :param version: specific version to base the computation on.
        :param exclude_payslip_ids: Payslip IDs to ignore when summing already-paid TDS.
        :param start_date: date to start applying TDS (later than contract/FY start).
        :return: Scheduled TDS amount (float) to deduct.
        """
        self.ensure_one()
        if self.company_id.country_code != 'IN':
            return {
                'income_tax_monthly': 0.0,
                'surcharge_monthly': 0.0,
                'cess_monthly': 0.0,
                'expected_tds': 0.0,
            }

        exclude_payslip_ids = set(exclude_payslip_ids or [])
        fy_start_date, fy_end_date = self._l10n_in_get_financial_year_bounds(reference_date=start_date)
        contract_start = version.contract_date_start or fy_start_date
        effective_date_start = max(contract_start, fy_start_date)
        tds_effective_date_start = max(effective_date_start, start_date) if start_date else effective_date_start

        payslips_by_version = self._l10n_in_collect_tax_payslips(
            fy_start_date,
            fy_end_date,
            exclude_payslip_ids=exclude_payslip_ids,
        )
        current_fy_payslips = self._l10n_in_get_grouped_payslips(payslips_by_version)
        current_version_payslips = payslips_by_version.get(version.id, self.env['hr.payslip'])
        declaration_values = self._l10n_in_prepare_tax_declaration_values(
            tds_effective_date_start,
            fy_end_date,
            version,
            current_fy_payslips,
            current_version_payslips,
        )
        expected_tds = declaration_values.get('expected_tds', 0.0)
        total_tds_tobe_paid = declaration_values.get('total_tds_tobe_paid', 0.0)
        if not expected_tds or not total_tds_tobe_paid:
            return {
                'income_tax_monthly': 0.0,
                'surcharge_monthly': 0.0,
                'cess_monthly': 0.0,
                'expected_tds': 0.0,
            }

        split_ratio = expected_tds / total_tds_tobe_paid
        surcharge_monthly = round((declaration_values.get('surcharge') or 0.0) * split_ratio, 2)
        cess_monthly = round((declaration_values.get('cess') or 0.0) * split_ratio, 2)
        income_tax_monthly = round(max(expected_tds - surcharge_monthly - cess_monthly, 0.0), 2)
        income_tax_monthly += round(expected_tds - (income_tax_monthly + surcharge_monthly + cess_monthly), 2)
        return {
            'income_tax_monthly': income_tax_monthly,
            'surcharge_monthly': surcharge_monthly,
            'cess_monthly': cess_monthly,
            'expected_tds': expected_tds,
        }

    def _l10n_in_build_tax_declaration(self, fy_date_start, fy_date_end):
        """Build the full tax declaration payload for each relevant contract version.

        :param requested_financial_year: Optional label to override the default FY.
        :return: List of declaration dicts (one per version) with amounts and formatted strings.
        """
        self.ensure_one()
        can_read_payroll_versions = (
            self.env.is_superuser()
            or self.env.user.has_group('hr_payroll.group_hr_payroll_user')
            or self.id in self.env.user.employee_ids.ids
        )
        if not can_read_payroll_versions:
            raise AccessError(_("You don't have access to view tax declarations. Please contact your administrator."))

        employee_versions = self.sudo().version_ids.filtered(lambda version_record: (
            version_record.contract_date_start and version_record.contract_date_start <= fy_date_end and
            (version_record.contract_date_end is False or version_record.contract_date_end >= fy_date_start)
        )).sorted(lambda version_record: (
            version_record.contract_date_start,
            version_record.date_version,
            version_record.id,
        ))
        if not employee_versions:
            return [], {}
        payslips_by_version = self._l10n_in_collect_tax_payslips(fy_date_start, fy_date_end)
        versions_to_compute = self.env['hr.version']
        declarations = []
        for version in employee_versions:
            versions_to_compute |= version
            grouped_payslips = self._l10n_in_get_grouped_payslips(payslips_by_version, versions=versions_to_compute)
            effective_date_start = max(version.contract_date_start, fy_date_start)
            declaration_values = self._l10n_in_prepare_tax_declaration_values(
                effective_date_start,
                fy_date_end,
                version,
                grouped_payslips,
                payslips_by_version.get(version, self.env['hr.payslip']),
            )
            declarations.append(declaration_values)
        contract_periods = {
            (declaration['contract_date_start'], declaration['contract_date_end'] or False)
            for declaration in declarations
        }
        return declarations, contract_periods

    def l10n_in_get_tax_declaration_view_data(self, financial_year=None):
        options = self._l10n_in_get_financial_year_selection()
        option_values = [value for value, _ in options]
        selected_financial_year = financial_year or option_values[0]
        fy_date_start, fy_date_end = self._l10n_in_get_financial_year_bounds(financial_year=selected_financial_year)
        declarations, contract_periods = self._l10n_in_build_tax_declaration(fy_date_start, fy_date_end)
        return {
            'financial_year_options': [{'value': value, 'label': label} for value, label in options],
            'financial_year': selected_financial_year,
            'declarations': declarations,
            'contract_count': len(contract_periods),
            'version_count': len(declarations),
            'fy_date_start': fy_date_start.strftime('%d/%m/%Y'),
            'fy_date_end': fy_date_end.strftime('%d/%m/%Y'),
        }

    def l10n_in_get_tax_declaration_report_action(self, financial_year):
        fy_date_start, fy_date_end = self._l10n_in_get_financial_year_bounds(financial_year=financial_year)
        declarations, contract_periods = self._l10n_in_build_tax_declaration(fy_date_start, fy_date_end)
        if not declarations:
            raise UserError(self.env._("No tax declaration data available for this financial year."))
        report_data = {
            'declarations': declarations,
            'financial_year': financial_year,
            'employee_id': self.id,
            'contract_count': len(contract_periods),
            'version_count': len(declarations),
            'fy_date_start': fy_date_start.strftime('%d/%m/%Y'),
            'fy_date_end': fy_date_end.strftime('%d/%m/%Y'),
        }
        action = self.env.ref('l10n_in_hr_payroll.action_report_tax_declaration_history')
        return action.report_action(self, data=report_data)
