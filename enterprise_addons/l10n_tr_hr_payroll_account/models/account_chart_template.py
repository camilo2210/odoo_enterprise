# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_tr(self, companies):
        salary_payable = 'tr320100'
        stamp_tax_deduction = 'tr320200'
        ssi_employee_contribution = 'tr320300'
        ssi_company_payable = 'tr320400'
        employee_income_tax = 'tr320500'
        basic_salary = 'tr702000'
        staff_other_allowances = 'tr702300'
        salary_deductions = 'tr702400'
        ssi_company_contribution = 'tr702500'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           TR Employee Payroll Structure          #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary').id),
            ('code', '=', 'BASIC')
        ], limit=1)
        rules_mapping[basic_rule]['debit'] = basic_salary

        ssie_rule = self.env.ref('l10n_tr_hr_payroll.turkey_salary_rule_ssie')
        rules_mapping[ssie_rule]['debit'] = ssi_employee_contribution

        ssic_rule = self.env.ref('l10n_tr_hr_payroll.turkey_ssi_company_contribution')
        rules_mapping[ssic_rule]['debit'] = ssi_company_contribution
        rules_mapping[ssic_rule]['credit'] = ssi_company_payable

        for xml_id in [
            'l10n_tr_hr_payroll_structure_tr_employee_salary_attachment_of_salary_rule',
            'l10n_tr_hr_payroll_structure_tr_employee_salary_assignment_of_salary_rule',
        ]:
            rule = self.env.ref(f'l10n_tr_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = salary_deductions

        child_support_rule = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_child_support')
        rules_mapping[child_support_rule]['debit'] = staff_other_allowances

        net_tax_deduction_rule = self.env.ref('l10n_tr_hr_payroll.turkey_net_tax_deduction')
        rules_mapping[net_tax_deduction_rule]['debit'] = employee_income_tax

        deduction_rule = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_deduction_salary_rule')
        rules_mapping[deduction_rule]['debit'] = salary_deductions

        reimbursement_rule = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_reimbursement_salary_rule')
        rules_mapping[reimbursement_rule]['debit'] = salary_payable

        stamp_tax_deduction_rule = self.env.ref('l10n_tr_hr_payroll.turkey_stamp_tax_deduction')
        rules_mapping[stamp_tax_deduction_rule]['debit'] = stamp_tax_deduction

        manual_deduction_rule = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_manual_deduction')
        rules_mapping[manual_deduction_rule]['debit'] = salary_deductions

        manual_addition_rule = self.env.ref('l10n_tr_hr_payroll.l10n_tr_hr_payroll_structure_tr_employee_salary_manual_addition')
        rules_mapping[manual_addition_rule]['debit'] = staff_other_allowances

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_tr_hr_payroll.hr_payroll_structure_tr_employee_salary').id),
            ('code', '=', 'NET')
        ], limit=1)
        rules_mapping[net_rule]['credit'] = salary_payable

        self._configure_payroll_account(
            companies,
            "TR",
            account_refs=[
                salary_payable, stamp_tax_deduction, ssi_employee_contribution, ssi_company_payable,
                employee_income_tax, basic_salary, staff_other_allowances, salary_deductions, ssi_company_contribution
            ],
            rules_mapping=rules_mapping,
            default_account=salary_payable
        )
