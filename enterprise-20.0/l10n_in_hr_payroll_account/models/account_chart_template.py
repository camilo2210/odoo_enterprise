# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_in(self, companies):
        salary_expense = 'p2101'
        hra_expense = 'p300001'
        standard_allowance_expense = 'p300002'
        fixed_allowance_expense = 'p300004'
        performance_bonus = 'p300005'
        employee_reimbursement_expense = 'p300006'
        pf_employee_payable = 'p300007'
        pf_employer_payable = 'p300008'
        advance_to_employee = 'p300009'
        salary_exp_payable = 'p300010'
        lta_expense = 'p300011'
        pt_payable = 'p300012'
        gratuity_control = 'p300013'
        esic_employee_payable = 'p300014'
        esic_employer_payable = 'p300015'
        lwf_employee_payable = 'p300016'
        lwf_employer_payable = 'p300017'
        medical_insurance_payable = 'p300018'
        tds_employee_payable = 'p300019'
        phone_subscription_payable = 'p300020'
        internet_subscription_payable = 'p300021'
        meal_vouchers_payable = 'p300022'
        company_transport_payable = 'p300023'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           IN Employee Payroll Structure          #
        # ================================================ #

        basic_IN_emp_salary_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_IN_emp_salary_rule]['debit'] = salary_expense

        hra_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_hra')
        rules_mapping[hra_IN_emp_salary_rule]['debit'] = hra_expense

        std_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_std')
        rules_mapping[std_IN_emp_salary_rule]['debit'] = standard_allowance_expense

        spl_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_spl')
        rules_mapping[spl_IN_emp_salary_rule]['debit'] = fixed_allowance_expense

        performance_bolus_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_p_bonus')
        rules_mapping[performance_bolus_IN_emp_salary_rule]['debit'] = performance_bonus

        lta_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_lta')
        rules_mapping[lta_IN_emp_salary_rule]['debit'] = lta_expense

        reimbursement_IN_salary_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary').id),
            ('code', '=', 'REIMBURSEMENT')
        ], limit=1)
        rules_mapping[reimbursement_IN_salary_rule]['debit'] = employee_reimbursement_expense

        expenses_reimbursement_IN_salary_rule = self.env.ref(
            'l10n_in_hr_payroll.l10n_in_hr_salary_rule_expenses_reimbursement')
        rules_mapping[expenses_reimbursement_IN_salary_rule]['debit'] = employee_reimbursement_expense

        pt_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_pt')
        rules_mapping[pt_IN_emp_salary_rule]['debit'] = pt_payable

        pf_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.hr_salary_rule_pf_with_pf')
        rules_mapping[pf_IN_emp_salary_rule]['debit'] = pf_employee_payable

        epf_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.hr_salary_rule_pfe_with_pf')
        rules_mapping[epf_IN_emp_salary_rule]['debit'] = pf_employer_payable

        attach_salary_IN_salary_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary').id),
            ('code', '=', 'ATTACH_SALARY')
        ], limit=1)
        rules_mapping[attach_salary_IN_salary_rule]['credit'] = advance_to_employee

        Deduction_IN_salary_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary').id),
            ('code', '=', 'DEDUCTION')
        ], limit=1)
        rules_mapping[Deduction_IN_salary_rule]['credit'] = salary_expense

        net_IN_salary_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_employee_salary').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_IN_salary_rule]['credit'] = salary_exp_payable

        gratuity_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_gratuity')
        rules_mapping[gratuity_IN_emp_salary_rule]['debit'] = gratuity_control

        esics_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_employee_esics')
        rules_mapping[esics_IN_emp_salary_rule]['debit'] = esic_employee_payable

        esicf_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_employer_esicf')
        rules_mapping[esicf_IN_emp_salary_rule]['debit'] = esic_employer_payable

        lwfe_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_lwf_employee')
        rules_mapping[lwfe_IN_emp_salary_rule]['debit'] = lwf_employee_payable

        lwf_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_lwf_employer')
        rules_mapping[lwf_IN_emp_salary_rule]['debit'] = lwf_employer_payable

        med_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_med')
        rules_mapping[med_IN_emp_salary_rule]['debit'] = medical_insurance_payable

        tds_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_payslip_rule_tds')
        rules_mapping[tds_IN_emp_salary_rule]['debit'] = tds_employee_payable

        phone_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_phone')
        rules_mapping[phone_IN_emp_salary_rule]['debit'] = phone_subscription_payable

        internet_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_internet')
        rules_mapping[internet_IN_emp_salary_rule]['debit'] = internet_subscription_payable

        meal_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_meal_vouchers')
        rules_mapping[meal_IN_emp_salary_rule]['debit'] = meal_vouchers_payable

        transport_IN_emp_salary_rule = self.env.ref('l10n_in_hr_payroll.l10n_in_hr_salary_rule_company_transport')
        rules_mapping[transport_IN_emp_salary_rule]['debit'] = company_transport_payable

        # ================================================ #
        #           IN Stipend Payroll Structure           #
        # ================================================ #

        net_IN_stipend_salary_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_in_hr_payroll.hr_payroll_structure_in_stipend').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_IN_stipend_salary_rule]['credit'] = salary_exp_payable

        self._configure_payroll_account(
            companies,
            "IN",
            account_refs=[
                salary_expense, hra_expense, standard_allowance_expense, fixed_allowance_expense, performance_bonus,
                employee_reimbursement_expense, pf_employee_payable, pf_employer_payable, advance_to_employee,
                salary_exp_payable, lta_expense, pt_payable, gratuity_control, esic_employee_payable,
                esic_employer_payable, lwf_employee_payable, lwf_employer_payable, medical_insurance_payable,
                tds_employee_payable, phone_subscription_payable, internet_subscription_payable, meal_vouchers_payable,
                company_transport_payable
            ],
            rules_mapping=rules_mapping,
            default_account=False
        )

    def _configure_payroll_account_in_sch3(self, companies):
        return self._configure_payroll_account_in(companies)
