# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_iq_remaining_annual_leave_balance = fields.Float(compute="_compute_l10n_iq_remaining_annual_leave_balance",
        groups="hr_payroll.group_hr_payroll_user")
    l10n_iq_annual_leave_provision_eligibility = fields.Float(readonly=False, related='version_id.l10n_iq_annual_leave_provision_eligibility', inherited=True, groups="hr_payroll.group_hr_payroll_user")

    def _compute_l10n_iq_remaining_annual_leave_balance(self):
        iq_employees = self.filtered(lambda e: e.company_country_code == 'IQ')
        for employee in (self - iq_employees):
            employee.l10n_iq_remaining_annual_leave_balance = 0

        emp_per_company = iq_employees.grouped('company_id')
        annual_work_entry_type_allocation_data = ({
            company.id: company.l10n_iq_annual_work_entry_type_id.get_allocation_data(emp_per_company[company])
                for company in iq_employees.company_id
                if company.l10n_iq_annual_work_entry_type_id
        })

        for employee in iq_employees:
            company_data = annual_work_entry_type_allocation_data.get(employee.company_id.id, {})
            employee_allocation_data = company_data.get(employee, False)
            employee.l10n_iq_remaining_annual_leave_balance = employee_allocation_data[0][1]['remaining_leaves'] \
                if employee_allocation_data else 0
