# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_jo_standard(self, companies):
        payables = 'jo_account_200101'
        employee_income_tax = 'jo_account_200307'
        social_security_payable = 'jo_account_200308'
        leave_days_provision = 'jo_account_200502'
        end_of_service_provision = 'jo_account_200503'
        end_of_service_indemnity = 'jo_account_500202'
        basic_salary = 'jo_account_500301'
        housing_allowance = 'jo_account_500302'
        transportation_allowance = 'jo_account_500303'
        leave_salary = 'jo_account_500305'
        staff_other_allowances = 'jo_account_500308'
        salary_deductions = 'jo_account_500310'
        social_security_expenses = 'jo_account_500311'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           JO Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_jo_hr_payroll.hr_payroll_structure_jo_employee_salary').id),
            ('code', '=', 'BASIC'),
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = basic_salary

        house_rule = self.env.ref('l10n_jo_hr_payroll.jordan_housing_allowance_salary_rule')
        rules_mapping[house_rule]['debit'] = housing_allowance

        transportation_rule = self.env.ref('l10n_jo_hr_payroll.jordan_transportation_allowance_salary_rule')
        rules_mapping[transportation_rule]['debit'] = transportation_allowance

        other_allowances_rule = self.env.ref('l10n_jo_hr_payroll.jordan_other_allowances_salary_rule')
        rules_mapping[other_allowances_rule]['debit'] = staff_other_allowances

        sse_deduction_rule = self.env.ref('l10n_jo_hr_payroll.jordan_sse_deduction')
        rules_mapping[sse_deduction_rule]['debit'] = social_security_payable

        ssc_contribution_rule = self.env.ref('l10n_jo_hr_payroll.jordan_ssc_contribution')
        rules_mapping[ssc_contribution_rule]['debit'] = social_security_expenses
        rules_mapping[ssc_contribution_rule]['credit'] = social_security_payable

        sick_leave_deduction_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_sick_leave_unpaid')
        rules_mapping[sick_leave_deduction_rule]['debit'] = salary_deductions

        for xml_id in [
            'l10n_jo_hr_payroll_structure_jo_employee_salary_rest_days_overtime',
            'l10n_jo_hr_payroll_structure_jo_employee_salary_public_holidays_overtime',
            'l10n_jo_hr_payroll_structure_jo_employee_salary_week_days_overtime',
        ]:
            rule = self.env.ref(f'l10n_jo_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = staff_other_allowances

        end_service_provision_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_end_of_service_provision')
        rules_mapping[end_service_provision_rule]['debit'] = end_of_service_indemnity
        rules_mapping[end_service_provision_rule]['credit'] = end_of_service_provision

        annual_leave_provision_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_Annual_Leave_provision')
        rules_mapping[annual_leave_provision_rule]['debit'] = leave_salary
        rules_mapping[annual_leave_provision_rule]['credit'] = leave_days_provision

        tax_bracket_total_rule = self.env.ref('l10n_jo_hr_payroll.jordan_tax_tax_bracket_total')
        rules_mapping[tax_bracket_total_rule]['debit'] = employee_income_tax

        end_service_benefit_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_end_of_service_benefit')
        rules_mapping[end_service_benefit_rule]['debit'] = end_of_service_provision

        remaining_leave_compensation_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_remaining_leave_compensation')
        rules_mapping[remaining_leave_compensation_rule]['debit'] = leave_days_provision

        for xml_id in [
            'l10n_jo_hr_payroll_structure_jo_employee_salary_end_of_service_tax_deduction',
            'l10n_jo_hr_payroll_structure_jo_employee_salary_assignment_of_salary_rule',
            'l10n_jo_hr_payroll_structure_jo_employee_salary_child_support',
            'l10n_jo_hr_payroll_structure_jo_employee_salary_deduction_salary_rule',
        ]:
            rule = self.env.ref(f'l10n_jo_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_deductions

        reimbursement_rule = self.env.ref('l10n_jo_hr_payroll.l10n_jo_hr_payroll_structure_jo_employee_salary_reimbursement_salary_rule')
        rules_mapping[reimbursement_rule]['debit'] = payables

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_jo_hr_payroll.hr_payroll_structure_jo_employee_salary').id),
            ('code', '=', 'NET'),
        ], limit=1)
        rules_mapping[net_rule]['credit'] = payables

        self._configure_payroll_account(
            companies,
            "JO",
            account_refs=[
                payables, employee_income_tax, social_security_payable, leave_days_provision, end_of_service_provision,
                end_of_service_indemnity, basic_salary, housing_allowance, transportation_allowance, leave_salary,
                staff_other_allowances, salary_deductions, social_security_expenses
            ],
            rules_mapping=rules_mapping,
            default_account=payables
        )
