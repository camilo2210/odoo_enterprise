# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import fields, models, api


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_ae_annual_leave_days_taken = fields.Float(
        string="Annual Leave Days Consumed",
        help="Current year's number of consumed allocations of the annual leave time-off type defined in the payroll settings",
        groups="hr_payroll.group_hr_payroll_user",
        compute="_compute_l10n_ae_annual_leave_days")
    l10n_ae_housing_allowance = fields.Monetary(readonly=False, related="version_id.l10n_ae_housing_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_transportation_allowance = fields.Monetary(readonly=False, related="version_id.l10n_ae_transportation_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_other_allowances = fields.Monetary(readonly=False, related="version_id.l10n_ae_other_allowances", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_airfare_allowance = fields.Monetary(readonly=False, related="version_id.l10n_ae_airfare_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_is_dews_applied = fields.Boolean(readonly=False, related="version_id.l10n_ae_is_dews_applied", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_dews_emp_contribution = fields.Float(readonly=False, related="version_id.l10n_ae_dews_emp_contribution", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_number_of_leave_days = fields.Integer(readonly=False, related="version_id.l10n_ae_number_of_leave_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_is_computed_based_on_daily_salary = fields.Boolean(readonly=False, related="version_id.l10n_ae_is_computed_based_on_daily_salary", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_eos_daily_salary = fields.Float(readonly=False, related="version_id.l10n_ae_eos_daily_salary", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_ae_total_unpaid_days = fields.Float(
        string="Total Unpaid Days",
        groups="hr.group_hr_user",
        compute="_compute_l10n_ae_total_unpaid_days",
    )

    @api.model
    def _l10n_ae_get_employees_below_min_wage(self):
        uae_companies = self.env.companies.filtered(lambda c: c.country_id.code == 'AE')
        if not uae_companies:
            return self.env['hr.employee']
        employees = self.search([('company_id', 'in', uae_companies.ids), ('country_id.code', '=', 'AE')])
        return employees.filtered(lambda e: e.current_version_id._l10n_ae_is_below_min_wage())

    def _l10n_ae_get_worked_duration(self, date_to=False):
        """ Return the PAID duration that the employee has worked as (years, months, days)"""
        self.ensure_one()
        if (first_version_date := self._get_first_version_date()) and (date_to or self.version_id.date_end):
            unpaid_days = int(self.l10n_ae_total_unpaid_days)
            unpaid_hours = int((self.l10n_ae_total_unpaid_days % 1) * 24)
            adjustment_values = relativedelta(days=unpaid_days + (1 if unpaid_hours else 0)) + relativedelta(hours=unpaid_hours)
            diff = relativedelta((date_to or self.version_id.date_end) - adjustment_values, first_version_date)
            return diff.years, diff.months, (diff.days + (diff.hours / 24))
        return 0, 0, 0

    def _l10n_ae_get_worked_years(self):
        years, months, days = self._l10n_ae_get_worked_duration()
        return years + (months / 12) + (days / 365)

    def _compute_l10n_ae_total_unpaid_days(self):
        # In case of simulating the employees' departure for the EOS report, it is assumed that all the remaining work days till the report end date are paid
        departing_employee_ids = self.filtered(lambda e: e.version_id.date_end)
        start = min(e._get_first_version_date() for e in self)
        end = max((e.version_id.date_end for e in departing_employee_ids), default=fields.Date.today())
        work_entries_vals = self.version_ids.generate_work_entries(start, end)
        duration_by_employee = defaultdict(lambda: 0)
        for vals in work_entries_vals:
            if vals['work_entry_type_id'].code in ['SICKLEAVE0', '158.00', '000.00']:
                duration_by_employee[vals['employee_id']] += vals['duration']
        for employee in self:
            employee.l10n_ae_total_unpaid_days = duration_by_employee[employee] / (employee._get_hours_per_day(employee.version_id.date_start) or 8)

    def _compute_l10n_ae_annual_leave_days(self):
        if not self.ids:
            self.write({'l10n_ae_annual_leave_days_taken': 0})
            return
        leaves_per_employee = self.env['hr.leave']._read_group(
            domain=[
                ('work_entry_type_id', 'in', self.company_id.l10n_ae_annual_work_entry_type_id.ids),
                ('state', '=', 'validate'),
            ],
            groupby=['work_entry_type_id', 'employee_id'],
            aggregates=['number_of_days:sum']
        )
        mapped_data = {
            employee.id: days_taken
            for work_entry_type, employee, days_taken in leaves_per_employee
            if work_entry_type == employee.company_id.l10n_ae_annual_work_entry_type_id
        }
        for employee in self:
            employee.l10n_ae_annual_leave_days_taken = mapped_data.get(employee.id, 0)

    def notify_expiring_contract_work_permit(self):
        today = fields.Date.context_today(self)
        activity_type = self.env.ref('l10n_ae_hr_payroll.mail_activity_data_l10n_ae_probation_action', raise_if_not_found=False)
        ae_companies = self.env.companies.filtered(lambda c: c.country_code == 'AE' and c.l10n_ae_probation_period_duration > 0)

        company_employee_domains = []
        for company in ae_companies:
            target_date = today - relativedelta(months=company.l10n_ae_probation_period_duration)
            expired_date = target_date + relativedelta(days=company.contract_expiration_notice_period)
            company_employee_domains.append(
                [
                    "&",
                    "&",
                    "&",
                    ("company_id", "=", company.id),
                    ("contract_date_start", ">", target_date),
                    ("contract_date_start", "<", expired_date),
                    "|",
                    ("activity_ids", "=", False),
                    ("activity_ids.activity_type_id", "not in", activity_type.ids),
                ],
            )
        company_employee_domains = fields.Domain.OR(company_employee_domains)

        for employee in self.env['hr.employee'].with_context(active_test=False).search(company_employee_domains):
            employee.activity_schedule(
                activity_type_id=activity_type.id,
                summary=self.env._('Probation period completed'),
                note=self.env._(
                    "%(employee)s has completed their probation period. "
                    "Allocate the annual leave with the start date being %(start_date)s.",
                ) % {
                    'employee': employee.name,
                    'start_date': fields.Date.to_string(employee.contract_date_start),
                },
                user_id=employee.hr_responsible_id.id or self.env.user.id,
                date_deadline=today,
            )
        return super().notify_expiring_contract_work_permit()
