# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_eg(self, companies):
        payables = 'egy_account_220100'
        leave_days_provision = 'egy_account_220200'
        eos_provision = 'egy_account_220202'
        social_contribution_payable = 'egy_account_220700'
        income_tax_payable = 'egy_account_220800'
        basic_salary = 'egy_account_410100'
        housing_allowance = 'egy_account_410200'
        transportation_allowance = 'egy_account_410300'
        staff_other_allowances = 'egy_account_410400'
        leave_salary = 'egy_account_410700'
        salary_deductions = 'egy_account_410900'
        eos_indemnity = 'egy_account_411900'
        social_contribution_company = 'egy_account_411901'

        rules_mapping = defaultdict(dict)

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = basic_salary

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_hr_payroll_structure_eg_employee_salary_deduction_salary_rule')
        rules_mapping[rule]['debit'] = salary_deductions

        for xml_id in [
            'egypt_other_allowances_salary_rule',
            'l10n_eg_hr_payroll_structure_eg_employee_salary_attachment_of_salary_rule',
            'l10n_eg_hr_payroll_structure_eg_employee_salary_assignment_of_salary_rule',
            'l10n_eg_hr_payroll_structure_eg_employee_salary_child_support',
        ]:
            rule = self.env.ref(f'l10n_eg_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = staff_other_allowances

        rule = self.env.ref('l10n_eg_hr_payroll.10n_eg_hr_payroll_structure_eg_employee_salary_housing_allowance')
        rules_mapping[rule]['debit'] = housing_allowance

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_transportation_allowance_salary_rule')
        rules_mapping[rule]['debit'] = transportation_allowance

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_social_insurance_contribution_company')
        rules_mapping[rule]['debit'] = social_contribution_company
        rules_mapping[rule]['credit'] = social_contribution_payable

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_social_insurance_contribution_employee')
        rules_mapping[rule]['debit'] = social_contribution_payable

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_end_of_service_provision_salary_rule')
        rules_mapping[rule]['debit'] = eos_indemnity
        rules_mapping[rule]['credit'] = eos_provision

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_salary_rule_annual_leave_provision')
        rules_mapping[rule]['debit'] = leave_salary
        rules_mapping[rule]['credit'] = leave_days_provision

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_salary_rule_annual_leave_compensation')
        rules_mapping[rule]['debit'] = leave_salary

        rule = self.env.ref('l10n_eg_hr_payroll.egypt_end_of_service_benefit_salary_rule')
        rules_mapping[rule]['debit'] = eos_provision

        for xml_id in [
            'egypt_tax_bracket_total',
            'l10n_eg_neg_tax_correction_salary_rule',
        ]:
            rule = self.env.ref(f'l10n_eg_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = income_tax_payable

        rule = self.env.ref('l10n_eg_hr_payroll.l10n_eg_pos_tax_correction_salary_rule')
        rules_mapping[rule]['credit'] = income_tax_payable

        for xml_id in [
            'l10n_eg_hr_payroll_structure_eg_employee_salary_reimbursement_salary_rule',
            'l10n_eg_hr_payroll_structure_eg_employee_salary_expenses_reimbursement',
        ]:
            rule = self.env.ref(f'l10n_eg_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = payables

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_rule]['credit'] = payables

        # ================================================ #
        #           EG Employee Payroll Structure          #
        # ================================================ #

        self._configure_payroll_account(
            companies,
            "EG",
            account_refs=[
                payables, leave_days_provision, eos_provision, social_contribution_payable, income_tax_payable,
                basic_salary, housing_allowance, transportation_allowance, staff_other_allowances, leave_salary,
                salary_deductions, eos_indemnity, social_contribution_company
            ],
            rules_mapping=rules_mapping,
            default_account=basic_salary
        )
