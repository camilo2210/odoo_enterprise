# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_hk(self, companies):
        mpf_accrued_employer = 'l10n_hk_221300'
        mpf_withheld_employee = 'l10n_hk_221400'
        tax_withheld = 'l10n_hk_221500'
        staff_housing_accrued = 'l10n_hk_221600'
        other_payable = 'l10n_hk_220200'
        salaries_wages_payable = 'l10n_hk_221200'
        sales_commission = 'l10n_hk_525200'
        mpf_contribution_employer = 'l10n_hk_521300'
        wages_salaries = 'l10n_hk_521100'
        bonus_payment = 'l10n_hk_521200'
        employee_benefits = 'l10n_hk_521400'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #          HK Employee Payroll Structure           #
        # ================================================ #

        for employee_type in ('regular', 'casual'):
            if rule := self.env.ref(f'l10n_hk_hr_payroll.cap57_{employee_type}_employees_salary_eemc', raise_if_not_found=False):
                rules_mapping[rule]['debit'] = mpf_withheld_employee

            if rule := self.env.ref(f'l10n_hk_hr_payroll.cap57_{employee_type}_employees_salary_ermc', raise_if_not_found=False):
                rules_mapping[rule]['debit'] = mpf_accrued_employer
                rules_mapping[rule]['credit'] = mpf_contribution_employer

            if rule := self.env.ref(f'l10n_hk_hr_payroll.cap57_{employee_type}_employees_salary_eevc', raise_if_not_found=False):
                rules_mapping[rule]['debit'] = mpf_withheld_employee

            if rule := self.env.ref(f'l10n_hk_hr_payroll.cap57_{employee_type}_employees_salary_ervc', raise_if_not_found=False):
                rules_mapping[rule]['debit'] = mpf_accrued_employer
                rules_mapping[rule]['credit'] = mpf_contribution_employer

            if rule := self.env.ref(f'l10n_hk_hr_payroll.cap57_{employee_type}_employees_salary_ervc_two', raise_if_not_found=False):
                rules_mapping[rule]['debit'] = mpf_accrued_employer
                rules_mapping[rule]['credit'] = mpf_contribution_employer

        if rule := self.env.ref('l10n_hk_hr_payroll.cap57_employees_employees_salary_fixed_commission', raise_if_not_found=False):
            rules_mapping[rule]['debit'] = sales_commission

        if rule := self.env.ref('l10n_hk_hr_payroll.cap57_employees_employees_salary_internet', raise_if_not_found=False):
            rules_mapping[rule]['debit'] = employee_benefits

        if rule := self.env.ref('l10n_hk_hr_payroll.cap57_employees_employees_salary_referral_fee', raise_if_not_found=False):
            rules_mapping[rule]['debit'] = bonus_payment

        if rule := self.env.ref('l10n_hk_hr_payroll.cap57_employees_employees_salary_end_of_year_payment', raise_if_not_found=False):
            rules_mapping[rule]['debit'] = bonus_payment

        if rule := self.env.ref('l10n_hk_hr_payroll.cap57_employees_employees_salary_expense_refund', raise_if_not_found=False):
            rules_mapping[rule]['debit'] = other_payable

        if rule := self.env.ref('l10n_hk_hr_payroll.cap57_employees_employees_employer_paid_rent', raise_if_not_found=False):
            rules_mapping[rule]['debit'] = employee_benefits
            rules_mapping[rule]['credit'] = staff_housing_accrued

        rule = self.env.ref('l10n_hk_hr_payroll.cap57_non_employees_salary_fixed_commission')
        rules_mapping[rule]['debit'] = sales_commission

        rule = self.env.ref('l10n_hk_hr_payroll.cap57_non_employees_salary_withheld')
        rules_mapping[rule]['debit'] = tax_withheld

        struct_ids = (
            self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
            self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_casual_employee_salary').id,
            self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_non_employee_salary').id,
        )
        net_rules = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', struct_ids),
            ('code', '=', 'NET')
        ])
        for net_rule in net_rules:
            rules_mapping[net_rule]['credit'] = salaries_wages_payable

        self._configure_payroll_account(
            companies,
            "HK",
            account_refs=[
                mpf_accrued_employer, mpf_withheld_employee, tax_withheld, staff_housing_accrued, other_payable,
                salaries_wages_payable, sales_commission, mpf_contribution_employer, wages_salaries, bonus_payment,
                employee_benefits
            ],
            rules_mapping=rules_mapping,
            default_account=wages_salaries
        )
