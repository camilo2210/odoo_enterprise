# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ae(self, companies):
        payables = 'uae_account_230100'
        eos_provision = 'uae_account_220102'
        basic_salary = 'uae_account_410100'
        housing_allowance = 'uae_account_410200'
        transportation_allowance = 'uae_account_410300'
        eos_indemnity = 'uae_account_411900'
        other_allowances = 'uae_account_410400'
        salary_deductions = 'uae_account_400500'
        leave_salary = 'uae_account_410700'
        social_insurance_expense = 'uae_account_400400'
        social_insurance_payable = 'uae_account_220103'
        dews_payable = 'uae_account_220104'
        leave_days_provision = 'uae_account_220100'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #          UAE Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = basic_salary

        for xml_id in [
            # United Arab Emirates: Regular Pay Structure
            'uae_salary_rule_input_housing_allowance',
            'uae_salary_rule_conveyance_allowance',
            'uae_salary_rule_medical_allowance',
            'uae_salary_rule_annual_passage_allowance',
            'uae_salary_rule_overtime_allowance',
            'uae_salary_rule_other_allowance',
            'uae_salary_rule_leave_encashment',
            'uae_salary_arrears_salary_rule',
            'uae_other_earnings_salary_rule',
            'uae_bonus_salary_rule',
            'uae_airfare_allowance_salary_rule',
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_child_support',
            'uae_other_allowances_salary_rule',
            # United Arab Emirates: Instant Pay Structure
            'l10n_ae_uae_instant_pay_allowance',
            'l10n_ae_uae_instant_pay_commission',
            'l10n_ae_uae_instant_pay_salary_advance',
            'l10n_ae_uae_instant_pay_loan_advance',
        ]:
            rule = self.env.ref(f'l10n_ae_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = other_allowances

        for xml_id in [
            # United Arab Emirates: Regular Pay Structure
            'uae_salary_deduction_salary_rule',
            'uae_other_deduction_salary_rule',
            'uae_employee_payroll_structure_sick_leave',
            'uae_unpaid_leave_salary_rule',
            'uae_out_of_contract_salary_rule',
            'l10n_ae_uae_employee_payroll_structure_advance_recovery',
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_attachment_of_salary_rule',
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_assignment_of_salary_rule',
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_deduction_salary_rule',
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_dews_employee_contribution',
            # United Arab Emirates: Instant Pay Structure
            'l10n_ae_uae_instant_pay_deduction',
        ]:
            rule = self.env.ref(f'l10n_ae_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_deductions

        house_rule = self.env.ref('l10n_ae_hr_payroll.uae_housing_allowance_salary_rule')
        rules_mapping[house_rule]['debit'] = housing_allowance

        transport_rule = self.env.ref('l10n_ae_hr_payroll.uae_transportation_allowance_salary_rule')
        rules_mapping[transport_rule]['debit'] = transportation_allowance

        end_rule = self.env.ref('l10n_ae_hr_payroll.uae_end_of_service_salary_rule')
        rules_mapping[end_rule]['debit'] = eos_provision

        provision_correction_rule = self.env.ref('l10n_ae_hr_payroll.uae_end_of_service_provision_correction_salary_rule')
        rules_mapping[provision_correction_rule]['debit'] = eos_provision
        rules_mapping[provision_correction_rule]['credit'] = eos_indemnity

        provision_rule = self.env.ref('l10n_ae_hr_payroll.uae_end_of_service_provision_salary_rule')
        rules_mapping[provision_rule]['debit'] = eos_indemnity
        rules_mapping[provision_rule]['credit'] = eos_provision

        leave_provision_rule = self.env.ref('l10n_ae_hr_payroll.uae_annual_leave_provision_salary_rule')
        rules_mapping[leave_provision_rule]['debit'] = leave_salary
        rules_mapping[leave_provision_rule]['credit'] = leave_days_provision

        social_company_contribution_rule = self.env.ref('l10n_ae_hr_payroll.uae_social_insurance_company_contribution_salary_rule')
        rules_mapping[social_company_contribution_rule]['debit'] = social_insurance_expense
        rules_mapping[social_company_contribution_rule]['credit'] = social_insurance_payable

        social_employee_contribution_rule = self.env.ref('l10n_ae_hr_payroll.uae_social_insurance_employee_contribution_salary_rule')
        rules_mapping[social_employee_contribution_rule]['debit'] = social_insurance_payable

        dews_comp_rule = self.env.ref('l10n_ae_hr_payroll.l10n_ae_hr_payroll_uae_employee_payroll_structure_dews_company_contribution')
        rules_mapping[dews_comp_rule]['credit'] = dews_payable

        for xml_id in [
            'uae_annual_leaves_eos_allowance_salary_rule',
            'uae_annual_leaves_eos_deduction_salary_rule',
        ]:
            rule = self.env.ref(f'l10n_ae_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = leave_days_provision

        for xml_id in [
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_reimbursement_salary_rule',
            'l10n_ae_hr_payroll_uae_employee_payroll_structure_expenses_reimbursement',
        ]:
            rule = self.env.ref(f'l10n_ae_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = payables

        instant_pay_net_rule = self.env.ref('l10n_ae_hr_payroll.l10n_ae_uae_instant_pay_net_salary')
        rules_mapping[instant_pay_net_rule]['credit'] = payables

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_ae_hr_payroll.uae_employee_payroll_structure').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_rule]['credit'] = payables

        self._configure_payroll_account(
            companies,
            "AE",
            account_refs=[
                payables, eos_provision, basic_salary, housing_allowance, transportation_allowance, eos_indemnity,
                other_allowances, salary_deductions, leave_salary, social_insurance_expense, social_insurance_payable,
                dews_payable, leave_days_provision
            ],
            rules_mapping=rules_mapping,
            default_account=basic_salary
        )
