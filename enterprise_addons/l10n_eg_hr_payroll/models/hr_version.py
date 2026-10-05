# Part of Odoo. See LICENSE file for full copyright and licensing details.

from calendar import monthrange
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_eg_eligible_for_eos = fields.Boolean(
        string='Eligible for End of Service', groups="hr_payroll.group_hr_payroll_user",
        help='If checked, the employee will be eligible to receive an end-of-service benefit upon departure')
    l10n_eg_number_of_years = fields.Float(groups="hr_payroll.group_hr_payroll_user", compute='_compute_number_of_years', default=0)
    l10n_eg_social_insurance_reference = fields.Monetary(string='Social Insurance Reference Amount', groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Portion of the employee's salary taken as the basis for social insurance deductions.")
    l10n_eg_housing_allowance = fields.Monetary(string='Egypt Housing Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_eg_transportation_allowance = fields.Monetary(string='Egypt Transportation Allowance', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_eg_other_allowances = fields.Monetary(string='Egypt Other Allowances', groups="hr_payroll.group_hr_payroll_user", tracking=1)
    l10n_eg_total_leave_days = fields.Float(string='Eligibility Per Year', default=21, groups="hr_payroll.group_hr_payroll_user", tracking=1,
        help="Number of annual leave days the employee is entitled to for the current year. This value is used in the annual leave provision calculation.")

    @api.depends('employee_id.departure_date')
    def _compute_number_of_years(self):
        today = fields.Date.context_today(self)
        for version in self:
            start_date = version.employee_id._get_first_version_date()
            end_date = version.employee_id.departure_date or today
            worked_period = relativedelta(end_date, start_date)

            days_in_month = monthrange(end_date.year, end_date.month)[1]
            version.l10n_eg_number_of_years = worked_period.years + (worked_period.months / 12) + (worked_period.days / days_in_month / 12)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "EG":
            whitelisted_fields += [
                "l10n_eg_social_insurance_reference",
                "l10n_eg_housing_allowance",
                "l10n_eg_transportation_allowance",
                "l10n_eg_other_allowances",
                "l10n_eg_total_leave_days",
            ]
        return whitelisted_fields
