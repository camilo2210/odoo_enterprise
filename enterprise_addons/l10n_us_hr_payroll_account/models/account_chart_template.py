# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_us(self, companies):
        salaries = 'account_account_us_salaries'
        salary_payable = 'account_account_us_salary_payable'
        employee_taxes = 'account_account_us_employee_payroll_taxes'
        employer_taxes = 'account_account_us_employer_payroll_taxes'
        payroll_tax = 'account_account_us_payroll_tax'

        rules_mapping = defaultdict(dict)

        payroll_taxes_rules = self.env['hr.salary.rule'].search([
            ('category_ids', 'in', self.env.ref('l10n_us_hr_payroll.hr_payroll_taxes').ids),
        ])
        for rule in payroll_taxes_rules:
            rules_mapping[rule]['debit'] = employee_taxes

        employer_deduction_rules = self.env['hr.salary.rule'].search([
            ('category_ids', 'in', self.env.ref('l10n_us_hr_payroll.hr_payroll_employer_deductions').ids),
        ])
        for rule in employer_deduction_rules:
            rules_mapping[rule]['debit'] = payroll_tax
            rules_mapping[rule]['credit'] = employer_taxes

        basic_rule = self.env.ref('l10n_us_hr_payroll.l10n_us_hr_payroll_structure_us_employee_salary_basic_salary_rule')
        rules_mapping[basic_rule]['debit'] = salaries

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_us_hr_payroll.hr_payroll_structure_us_employee_salary').id),
            ('code', '=', 'NET')
        ])
        rules_mapping[net_rule]['credit'] = salary_payable

        self._configure_payroll_account(
            companies,
            "US",
            account_refs=[
                salaries, salary_payable, employee_taxes, employer_taxes, payroll_tax
            ],
            rules_mapping=rules_mapping,
            default_account=salaries
        )
