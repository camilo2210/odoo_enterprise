# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import fields, models
from datetime import timedelta


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_sa_ssn = fields.Char('SA: Social Security Number', groups="hr.group_hr_user", tracking=True)
    l10n_sa_employee_code = fields.Char(string="National/IQAMA ID", groups="hr_payroll.group_hr_payroll_user",
                                        help="Provide the 10 characters long IQAMA number of the employee")
    l10n_sa_remaining_annual_leave_balance = fields.Float(compute="_compute_l10n_sa_remaining_annual_leave_balance",
        groups="hr_payroll.group_hr_payroll_user")

    l10n_sa_eos_number_of_days_in_year = fields.Selection(readonly=False, related="version_id.l10n_sa_eos_number_of_days_in_year", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_housing_allowance = fields.Monetary(readonly=False, related="version_id.l10n_sa_housing_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_transportation_allowance = fields.Monetary(readonly=False, related="version_id.l10n_sa_transportation_allowance", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_other_allowances = fields.Monetary(readonly=False, related="version_id.l10n_sa_other_allowances", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_number_of_days = fields.Integer(readonly=False, related="version_id.l10n_sa_number_of_days", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    l10n_sa_company_social_insurance_percentage = fields.Float(readonly=False, related="version_id.l10n_sa_company_social_insurance_percentage",
                                                               inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_company_oh_insurance_percentage = fields.Float(readonly=False, related="version_id.l10n_sa_company_oh_insurance_percentage",
                                                           inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_company_unemployment_insurance_percentage = fields.Float(readonly=False, related="version_id.l10n_sa_company_unemployment_insurance_percentage",
                                                                     inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_employee_social_insurance_percentage = fields.Float(readonly=False, related="version_id.l10n_sa_employee_social_insurance_percentage",
                                                                inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_employee_oh_insurance_percentage = fields.Float(readonly=False, related="version_id.l10n_sa_employee_oh_insurance_percentage",
                                                            inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_sa_employee_unemployment_insurance_percentage = fields.Float(readonly=False, related="version_id.l10n_sa_employee_unemployment_insurance_percentage",
                                                                      inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def _compute_l10n_sa_remaining_annual_leave_balance(self):
        sa_employees = self.filtered(lambda e: e.company_country_code == 'SA')
        for employee in (self - sa_employees):
            employee.l10n_sa_remaining_annual_leave_balance = 0

        emp_per_company = sa_employees.grouped('company_id')
        annual_work_entry_type_allocation_data = ({
            company.id: company.l10n_sa_annual_work_entry_type_id.get_allocation_data(emp_per_company[company])
                for company in sa_employees.company_id
                if company.l10n_sa_annual_work_entry_type_id
        })
        for employee in sa_employees:
            company_data = annual_work_entry_type_allocation_data.get(employee.company_id.id, {})
            employee_allocation_data = company_data.get(employee, False)
            employee.l10n_sa_remaining_annual_leave_balance = employee_allocation_data[0][1]['remaining_leaves'] \
                if employee_allocation_data else 0

    def _l10n_sa_get_number_of_years(self, start_date, end_date):
        self.ensure_one()
        version = self.version_id

        unpaid_leave_eos_threshold = self.company_id.l10n_sa_unpaid_leave_eos_threshold
        unpaid_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.id),
            ('state', '=', 'validate'),
            ('date_from', '>=', start_date),
            ('date_to', '<=', end_date),
            ('work_entry_type_id.amount_rate', '=', 0.0),
            ('number_of_days', '>=', unpaid_leave_eos_threshold)
        ])
        deducted_day_amount = 0
        for leave in unpaid_leaves:
            deducted_day_amount += leave.number_of_days - unpaid_leave_eos_threshold

        adjusted_end_date = end_date - timedelta(days=deducted_day_amount)
        worked_duration = relativedelta(adjusted_end_date, start_date)

        if version.l10n_sa_eos_number_of_days_in_year == 'actual':
            # 1 Day to be added as per the calculation in the QIWA calculator
            worked_duration += relativedelta(days=1)
            # last day of month is calculated to get the actual duration that the employee spent as years
            # without a need to approximate the days in a year.
            next_month = (end_date + relativedelta(months=1)).replace(day=1)
            last_day_of_month = (next_month - end_date.replace(day=1)).days
            total_years = worked_duration.years + (worked_duration.months / 12) + ((worked_duration.days / last_day_of_month) / 12)
        else:
            total_days = (end_date - start_date).days - deducted_day_amount
            total_years = total_days / int(version.l10n_sa_eos_number_of_days_in_year)
        return total_years

    def notify_expiring_contract_work_permit(self):
        today = fields.Date.context_today(self)
        activity_type = self.env.ref('l10n_sa_hr_payroll.mail_activity_data_l10n_sa_probation_action', raise_if_not_found=False)
        sa_companies = self.env.companies.filtered(lambda c: c.country_code == 'SA' and c.l10n_sa_probation_period_duration > 0)

        company_employee_domains = []
        for company in sa_companies:
            target_date = today - relativedelta(months=company.l10n_sa_probation_period_duration)
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
