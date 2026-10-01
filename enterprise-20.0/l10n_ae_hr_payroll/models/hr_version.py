# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from datetime import date
from math import ceil


class HrVersion(models.Model):
    _inherit = "hr.version"

    l10n_ae_housing_allowance = fields.Monetary(string="Housing Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_ae_transportation_allowance = fields.Monetary(string="Transportation Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_ae_other_allowances = fields.Monetary(string="Other Allowances", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_ae_airfare_allowance = fields.Monetary(string="Airfare Allowance", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_ae_total_salary = fields.Monetary(string="Total Salary", groups="hr_payroll.group_hr_payroll_user",
                                           compute="_compute_total_salary", help="Used in salary rules and on printouts")
    l10n_ae_is_dews_applied = fields.Boolean(string="Is DEWS Applied", groups="hr_payroll.group_hr_payroll_user",
                                             help="Daman Investments End of Service Programme", tracking=1)
    l10n_ae_number_of_leave_days = fields.Integer(string="Eligibility", default=30, groups="hr_payroll.group_hr_payroll_user", tracking=1,
                                                  help="The number of annual leave days an employee is entitled to for one year of service")
    l10n_ae_dews_emp_contribution = fields.Float(
        default=0.0,
        string="Employee contribution",
        groups="hr_payroll.group_hr_payroll_user",
        help="Daman Investments employee's contribution in percentage",
    )
    l10n_ae_is_computed_based_on_daily_salary = fields.Boolean(string="Computed Based On Daily Salary", groups="hr_payroll.group_hr_payroll_user", tracking=1,
                                                               help="If True, The EOS will be computed based on the daily salary provided rather than the basic salary")
    l10n_ae_eos_daily_salary = fields.Float(string="Daily Salary", groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_ae_pansion_enrollment_date = fields.Date(
        string="Pension Enrollment Date",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=1,
        help="First enrollment date for Pension programm Determines whether pre or post 2023 pension regulations apply under GPSSA and ADPF rules")
    l10n_ae_mohre_skill_level = fields.Selection(groups="hr.group_hr_user", related="job_id.l10n_ae_mohre_skill_level")

    _l10n_ae_hr_payroll_number_of_leave_days_constraint = models.Constraint(
        'CHECK(l10n_ae_number_of_leave_days >= 0)',
        "Number of Leave Days must be equal to or greater than 0",
    )

    _l10n_ae_hr_payroll_dews_emp_contribution_constraint = models.Constraint(
        "CHECK(l10n_ae_dews_emp_contribution >= 0.0 AND l10n_ae_dews_emp_contribution <= 0.10)",
        "The employee contribution must be greater than or equal to 0 and less than or equal to 10.",
    )

    def _l10n_ae_is_below_min_wage(self):
        self.ensure_one()
        min_wage = self.env['hr.rule.parameter']._get_parameter_from_code("l10n_ae_min_wage", date(2026, 1, 1), False)
        if not min_wage:
            return False
        # TODO Handle hourly/monthly/quarterly etc convertion
        monthly_wage = self.wage
        return self.contract_date_start >= date(2026, 1, 1) and monthly_wage < min_wage

    @api.depends('wage', 'l10n_ae_housing_allowance', 'l10n_ae_transportation_allowance', 'l10n_ae_other_allowances')
    def _compute_total_salary(self):
        for contract in self:
            contract.l10n_ae_total_salary = contract.wage + contract.l10n_ae_housing_allowance + contract.l10n_ae_transportation_allowance + contract.l10n_ae_other_allowances

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template()
        if self.env.company.country_id.code == "AE":
            whitelisted_fields += [
                "l10n_ae_eos_daily_salary",
                "l10n_ae_housing_allowance",
                "l10n_ae_is_computed_based_on_daily_salary",
                "l10n_ae_is_dews_applied",
                "l10n_ae_number_of_leave_days",
                "l10n_ae_other_allowances",
                "l10n_ae_transportation_allowance",
            ]
        return whitelisted_fields

    def _l10n_ae_get_eos_compensation(self, at_date=False):
        self.ensure_one()
        employee = self.employee_id
        years, months, days = employee._l10n_ae_get_worked_duration(at_date)

        salary = 0
        if self.l10n_ae_is_computed_based_on_daily_salary:
            salary = self.l10n_ae_eos_daily_salary * 30
        else:
            salary = self.wage

        total_months = years * 12 + months

        # compensation for time less than 5 years
        sub5_ratio = 21 / 30
        compensation_sub5_day = (salary * sub5_ratio) / 365
        compensation_sub5_month = (salary * sub5_ratio) / 12

        # compensation for time more than 5 years
        compensation_after5_day = salary / 365
        compensation_after5_month = salary / 12

        if total_months < 12:
            result = 0
        elif total_months < (6 * 12):
            result = ceil(compensation_sub5_month * total_months) + ceil(compensation_sub5_day * days)
        else:
            result = ceil(compensation_sub5_month * 60) + ceil(compensation_after5_month * (total_months - 60)) + ceil(compensation_after5_day * days)
        return result
