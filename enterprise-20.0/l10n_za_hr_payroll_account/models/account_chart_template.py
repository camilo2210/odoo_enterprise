# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_za(self, companies):
        paye_uif_payable = '220030'
        net_wages = '220040'
        medical_scheme_payable = '220070'
        other_deductions_payable = '220080'
        gross_salary = '610090'
        employer_sdl_uif_expense = '610100'

        rules_mapping = defaultdict(dict)

        # ==================================== #
        #      South Africa: Regular Pay       #
        # ==================================== #

        gross = self.env.ref('l10n_za_hr_payroll.l10n_za_hr_payroll_structure_za_employee_salary_gross_salary_rule')
        rules_mapping[gross]['debit'] = gross_salary

        # Employee PAYE
        paye = self.env.ref('l10n_za_hr_payroll.l10n_za_employees_salary_paye')
        rules_mapping[paye]['credit'] = paye_uif_payable

        # Employee UIF
        employee_uif = self.env.ref('l10n_za_hr_payroll.l10n_za_employees_salary_uif')
        rules_mapping[employee_uif]['credit'] = paye_uif_payable

        # Medical Scheme Contribution
        medical_scheme = self.env.ref('l10n_za_hr_payroll.l10n_za_employees_salary_medical_scheme_contribution')
        rules_mapping[medical_scheme]['credit'] = medical_scheme_payable

        # Other Deductions
        other_deductions = self.env.ref('l10n_za_hr_payroll.l10n_za_employees_deductions')
        rules_mapping[other_deductions]['credit'] = other_deductions_payable

        # Employer SDL
        employer_sdl = self.env.ref('l10n_za_hr_payroll.l10n_za_employer_salary_sdl')
        rules_mapping[employer_sdl]['debit'] = employer_sdl_uif_expense
        rules_mapping[employer_sdl]['credit'] = paye_uif_payable

        # Employer UIF
        employer_uif = self.env.ref('l10n_za_hr_payroll.l10n_za_employer_salary_uif')
        rules_mapping[employer_uif]['debit'] = employer_sdl_uif_expense
        rules_mapping[employer_uif]['credit'] = paye_uif_payable

        # Net Salary
        net = self.env.ref('l10n_za_hr_payroll.l10n_za_hr_payroll_structure_za_employee_salary_net_salary')
        rules_mapping[net]['credit'] = net_wages

        self._configure_payroll_account(
            companies,
            'ZA',
            account_refs=[
                paye_uif_payable,
                net_wages,
                medical_scheme_payable,
                other_deductions_payable,
                gross_salary,
                employer_sdl_uif_expense,
            ],
            rules_mapping=rules_mapping,
            default_account=gross_salary,
        )
