# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from datetime import date
import calendar

from odoo import api, fields, models
from odoo.tools import float_compare, formatLang


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_mx_daily_salary = fields.Float('MX: Daily Salary', compute='_compute_daily_salary')
    l10n_mx_years_worked = fields.Integer('MX: Years Worked', compute='_compute_l10n_mx_years_worked')
    l10n_mx_days_of_year = fields.Integer('MX: Days of the Year', compute='_compute_days_of_year')
    l10n_mx_integration_factor = fields.Float(
        string='MX: Integration Factor',
        readonly=False,
        store=True,
        compute='_compute_l10n_mx_integration_factor',
        inverse='_inverse_l10n_mx_integration_factor',
    )
    l10n_mx_is_integration_factor_manual = fields.Boolean()

    @api.depends('version_id.wage', 'version_id.schedule_pay')
    def _compute_daily_salary(self):
        for payslip in self:
            if not payslip.version_id or payslip.country_code != 'MX':
                payslip.l10n_mx_daily_salary = 0.0
            else:
                payslip.l10n_mx_daily_salary = payslip.version_id.wage / payslip._rule_parameter('l10n_mx_schedule_table')[payslip.version_id.schedule_pay]

    @api.depends('date_to')
    def _compute_days_of_year(self):
        for payslip in self:
            year = payslip.date_to.year
            payslip.l10n_mx_days_of_year = (date(year, 12, 31) - date(year, 1, 1)).days + 1

    @api.depends('date_from', 'date_to')
    def _compute_l10n_mx_years_worked(self):
        for payslip in self:
            start_date = (
                payslip.employee_id._get_first_contract_date(payslip.date_from)
                or payslip.employee_id._get_first_contract_date()
            )
            payslip.l10n_mx_years_worked = payslip.date_to.year - start_date.year
            if start_date <= payslip.date_to + relativedelta(year=start_date.year):
                payslip.l10n_mx_years_worked += 1

    @api.depends('l10n_mx_days_of_year', 'date_from', 'date_to', 'version_id')
    def _compute_l10n_mx_integration_factor(self):
        for payslip in self:
            if payslip.l10n_mx_is_integration_factor_manual:
                continue

            payslip.l10n_mx_integration_factor = payslip._get_l10n_mx_integration_factor()

    def _inverse_l10n_mx_integration_factor(self):
        for payslip in self:
            assigned = payslip.l10n_mx_integration_factor
            computed = payslip._get_l10n_mx_integration_factor()
            if float_compare(assigned, computed, precision_digits=4):
                payslip.l10n_mx_is_integration_factor_manual = True
                payslip.l10n_mx_integration_factor = assigned
                payslip._compute_issues()

    def action_reset_integration_factor(self):
        self.ensure_one()
        self.l10n_mx_is_integration_factor_manual = False
        self._compute_l10n_mx_integration_factor()
        self.compute_sheet()

    def _get_l10n_mx_integration_factor(self):
        self.ensure_one()

        if not self.version_id or self.country_code != 'MX':
            return 0.0

        holidays_count = self._rule_parameter('l10n_mx_holiday_tables')[self.l10n_mx_years_worked]
        holiday_bonus_factor = holidays_count * self.version_id.l10n_mx_holiday_bonus_rate

        number_of_days_year = self.l10n_mx_days_of_year

        return (
            holiday_bonus_factor
            + self.version_id.l10n_mx_christmas_bonus
            + number_of_days_year
        ) / number_of_days_year

    def write(self, vals):
        integration_factor_name = 'l10n_mx_integration_factor'
        digits = 4
        if integration_factor_name not in vals:
            return super().write(vals)

        old_values = {slip.id: slip.l10n_mx_integration_factor for slip in self}

        res = super().write(vals)

        for payslip in self:
            initial_value = old_values.get(payslip.id, 0.0)
            new_value = payslip.l10n_mx_integration_factor

            if float_compare(initial_value, new_value, precision_digits=4):
                integration_factor_field = self.env.ref('l10n_mx_hr_payroll.field_hr_payslip__l10n_mx_integration_factor')
                tracking_values = [{
                    'field_id': integration_factor_field.id,
                    'field_name': integration_factor_name,
                    'field_label': integration_factor_field.field_description,
                    'field_type': integration_factor_field.ttype,
                    'old_value': formatLang(self.env, initial_value, digits=digits, rounding_unit='decimals'),
                    'new_value': formatLang(self.env, new_value, digits=digits, rounding_unit='decimals'),
                    'old_value_float': initial_value,
                    'new_value_float': new_value,
                }]
                self._message_log(message_type='tracking', tracking_values=tracking_values)

        return res

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_mx_hr_payroll', [
                'data/hr_salary_rule_category_data.xml',
                'data/hr_payroll_structure_type_data.xml',
                'data/hr_payroll_structure_data.xml',
                'data/hr_rule_parameters_data.xml',
                'data/salary_rules/hr_salary_rule_christmas_bonus_data.xml',
                'data/salary_rules/hr_salary_rule_regular_pay_data.xml',
            ])]

    def _l10n_mx_get_previous_bimester_data(self):
        """
        Calculates the accrued days and retrieves payslips from the immediately preceding bimester.

        :return: A tuple (payslips, accrued_days)
            - payslips (hr.payslip): Recordset of paid/validated payslips in the bimester.
            - accrued_days (int): Total effective calendar days minus unpaid absences.
        """
        self.ensure_one()

        month_offset = -1 if self.date_from.month % 2 == 0 else 0
        bimester_start = self.date_from + relativedelta(months=-2 + month_offset, day=1)
        bimester_end = self.date_from + relativedelta(months=-1 + month_offset, day=31)

        bimester_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('structure_code', '=', 'MX_REGULAR'),
            ('state', 'in', ['paid', 'validated']),
            ('date_from', '>=', bimester_start),
            ('date_to', '<=', bimester_end),
        ])

        if not bimester_payslips:
            return bimester_payslips, 0

        unpaid_lines = bimester_payslips.worked_days_line_ids.filtered_domain([
            ('work_entry_type_id.amount_rate', '=', 0.0)
        ])
        total_unpaid_days = sum(unpaid_lines.mapped('number_of_days'))

        min_date_from = min(bimester_payslips.mapped('date_from'))
        max_date_to = max(bimester_payslips.mapped('date_to'))
        effective_start = max(min_date_from, bimester_start)
        effective_end = min(max_date_to, bimester_end)

        calendar_days = (effective_end - effective_start).days + 1
        accrued_days = calendar_days - total_unpaid_days

        return bimester_payslips, accrued_days

    def _get_payslips_in_month(self):
        self.ensure_one()
        first_day_of_month = self.date_from.replace(day=1)
        return self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('structure_code', '=', 'MX_REGULAR'),
            ('state', 'in', ['paid', 'validated']),
            ('date_to', '>=', first_day_of_month),
            ('date_from', '<', first_day_of_month + relativedelta(months=1))
        ])

    def _get_accumulated_monthly_subsidy(self):
        payslips_in_month = self._get_payslips_in_month()
        line_values = payslips_in_month._get_line_values(['SUBSIDY_CURRENT_MONTH', 'SUBSIDY_NEXT_MONTH'])

        accumulated_subsidy = 0.0
        for slip in payslips_in_month:
            subsidy_code = (
                'SUBSIDY_CURRENT_MONTH'
                if slip.date_from.month == self.date_from.month
                else 'SUBSIDY_NEXT_MONTH'
            )
            accumulated_subsidy += line_values[subsidy_code][slip.id]['total']

        return accumulated_subsidy

    @api.model
    def _schedule_timedelta(self, schedule, date_from, country_code=False):
        if country_code == 'MX':
            if schedule == '10_days':
                return relativedelta(days=9)
            elif schedule == '14_days':
                return relativedelta(days=13)
            elif schedule == 'bi-weekly':
                days_in_month = calendar.monthrange(date_from.year, date_from.month)[1]
                return relativedelta(day=15 if date_from.day <= 15 else days_in_month)
            elif schedule == 'bi-monthly':
                return relativedelta(months=2, days=-1)

        return super()._schedule_timedelta(schedule, date_from, country_code)

    def _get_out_of_period_duration(self, start, stop, reference_calendar):
        self.ensure_one()
        if self.country_code != 'MX':
            return super()._get_out_of_period_duration(start, stop, reference_calendar)

        days = (stop - start).days + 1
        return {
            'days': days,
            'hours': days * reference_calendar.hours_per_day,
        }

    def _get_schedule_days(self):
        self.ensure_one()
        if self.is_wrong_duration:
            return (self.date_to - self.date_from).days + 1
        return self._rule_parameter('l10n_mx_schedule_table')[self.version_id.schedule_pay]
