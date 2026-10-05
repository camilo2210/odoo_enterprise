# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_id(self, companies):
        employee_salary = 'l10n_id_61100010'
        tax_allowance_expense = 'l10n_id_61100050'
        bpjs_expense = 'l10n_id_61100060'
        accrued_payable_bpjs_ketenagakerjaan = 'l10n_id_25110020'
        accrued_payable_bpjs_kesehatan = 'l10n_id_25110110'
        tax_payable_pph_21 = 'l10n_id_21210010'
        salary_deposit = 'l10n_id_21100040'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           ID Employee Payroll Structure          #
        # ================================================ #

        # Income: Basic, fixed allowance, allowances, overtime and reimbursement
        for xml_id in (
            'l10n_id_hr_payroll_structure_id_employee_salary_basic_salary_rule',
            'l10n_id_hr_payroll_structure_id_employee_fixed_allowance_rule',
            'salary_rule_id_transport_allowance',
            'salary_rule_id_laptop',
            'salary_rule_id_incentive',
            'salary_rule_id_thr',
            'salary_rule_id_meal_allowance',
            'salary_rule_id_level_allowance',
            'l10n_id_hr_payroll_overtime_salary_rule',
            'l10n_id_hr_payroll_structure_id_employee_salary_reimbursement_salary_rule',
        ):
            rules_mapping[self.env.ref('l10n_id_hr_payroll.%s' % xml_id)]['debit'] = employee_salary

        # Company contributions (BPJS): expense vs accrued payable
        bpjs_jkk_rule = self.env.ref('l10n_id_hr_payroll.salary_rule_id_bpjs_jkk')
        rules_mapping[bpjs_jkk_rule]['debit'] = bpjs_expense
        rules_mapping[bpjs_jkk_rule]['credit'] = accrued_payable_bpjs_ketenagakerjaan

        bpjs_jkm_rule = self.env.ref('l10n_id_hr_payroll.salary_rule_id_bpjs_jkm')
        rules_mapping[bpjs_jkm_rule]['debit'] = bpjs_expense
        rules_mapping[bpjs_jkm_rule]['credit'] = accrued_payable_bpjs_ketenagakerjaan

        for xml_id in ('salary_rule_id_bpjs_kesehatan', 'salary_rule_id_bpjs_kesehatan_arrears'):
            bpjs_kesehatan_rule = self.env.ref('l10n_id_hr_payroll.%s' % xml_id)
            rules_mapping[bpjs_kesehatan_rule]['debit'] = bpjs_expense
            rules_mapping[bpjs_kesehatan_rule]['credit'] = accrued_payable_bpjs_kesehatan

        for xml_id in ('salary_rule_id_gross_up_bpjs_kesehatan_emp', 'salary_rule_id_gross_up_bpjs_kesehatan_emp_arrears'):
            bpjs_kesehatan_emp_rule = self.env.ref('l10n_id_hr_payroll.%s' % xml_id)
            rules_mapping[bpjs_kesehatan_emp_rule]['debit'] = '61100060'
            rules_mapping[bpjs_kesehatan_emp_rule]['credit'] = '25110110'

        jht_company_rule = self.env.ref('l10n_id_hr_payroll.salary_rule_id_gross_up_jht_company')
        rules_mapping[jht_company_rule]['debit'] = bpjs_expense
        rules_mapping[jht_company_rule]['credit'] = accrued_payable_bpjs_ketenagakerjaan

        jp_company_rule = self.env.ref('l10n_id_hr_payroll.salary_rule_id_gross_up_jp_company')
        rules_mapping[jp_company_rule]['debit'] = bpjs_expense
        rules_mapping[jp_company_rule]['credit'] = accrued_payable_bpjs_ketenagakerjaan

        # Tax allowance (Gross Up)
        tax_allowance_rule = self.env.ref('l10n_id_hr_payroll.l10n_id_hr_payroll_structure_id_employee_salary_tax_allowance')
        rules_mapping[tax_allowance_rule]['debit'] = tax_allowance_expense

        # Employee-borne deductions: charged against the accrued payable
        rules_mapping[self.env.ref('l10n_id_hr_payroll.salary_rule_id_jht')]['debit'] = accrued_payable_bpjs_ketenagakerjaan
        rules_mapping[self.env.ref('l10n_id_hr_payroll.salary_rule_id_jp')]['debit'] = accrued_payable_bpjs_ketenagakerjaan
        rules_mapping[self.env.ref('l10n_id_hr_payroll.salary_rule_id_bpjs_sehat_ded')]['debit'] = accrued_payable_bpjs_kesehatan
        rules_mapping[self.env.ref('l10n_id_hr_payroll.salary_rule_id_bpjs_sehat_ded_arrears')]['debit'] = accrued_payable_bpjs_kesehatan

        # PPh 21 tax
        rules_mapping[self.env.ref('l10n_id_hr_payroll.salary_rule_id_pph')]['debit'] = tax_payable_pph_21

        # Net salary payable
        net_rule = self.env.ref('l10n_id_hr_payroll.l10n_id_hr_payroll_structure_id_employee_salary_net_salary')
        rules_mapping[net_rule]['credit'] = salary_deposit

        self._configure_payroll_account(
            companies,
            "ID",
            account_refs=[
                employee_salary, tax_allowance_expense, bpjs_expense, accrued_payable_bpjs_ketenagakerjaan,
                accrued_payable_bpjs_kesehatan, tax_payable_pph_21, salary_deposit
            ],
            rules_mapping=rules_mapping,
            default_account=employee_salary
        )
