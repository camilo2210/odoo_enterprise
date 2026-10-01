# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ke(self, companies):
        paye_ni_payable = 'ke2210'
        net_wages = 'ke2220'
        pension_fund = 'ke2230'
        shif_payable = 'ke2231'
        helb_payable = 'ke2232'
        medical_insurance_payable = 'ke2233'
        life_insurance_payable = 'ke2234'
        education_insurance_payable = 'ke2235'
        gross_salary = 'ke5109'
        nssf_employer_expense = 'ke510910'
        ahl_employer_expense = 'ke510920'
        nita_employer_expense = 'ke510930'

        rules_mapping = defaultdict(dict)

        # ==================================== #
        #          Kenya: Regular Pay          #
        # ==================================== #

        gross = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_ke_hr_payroll.hr_payroll_structure_ken_employee_salary').id),
            ('code', '=', 'GROSS')
        ])
        rules_mapping[gross]['debit'] = gross_salary

        for xml_id in [
            'l10n_ke_employees_salary_ahl_amount',
            'l10n_ke_employees_salary_paye',
        ]:
            rule = self.env.ref(f'l10n_ke_hr_payroll.{xml_id}')
            rules_mapping[rule]['credit'] = paye_ni_payable

        nssf_amount = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_nssf_amount')
        rules_mapping[nssf_amount]['credit'] = pension_fund

        for xml_id in [
            'l10n_ke_employees_salary_nhif_amount',
            'l10n_ke_employees_salary_shif_amount',
        ]:
            rule = self.env.ref(f'l10n_ke_hr_payroll.{xml_id}')
            rules_mapping[rule]['credit'] = shif_payable

        helb = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_helb')
        rules_mapping[helb]['credit'] = helb_payable

        voluntary_medical_insurance = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_volontary_medical_insurance')
        rules_mapping[voluntary_medical_insurance]['credit'] = medical_insurance_payable

        life_insurance = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_life_insurance')
        rules_mapping[life_insurance]['credit'] = life_insurance_payable

        education = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_education')
        rules_mapping[education]['credit'] = education_insurance_payable

        pension_contribution = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employees_salary_pension_contribution')
        rules_mapping[pension_contribution]['credit'] = pension_fund

        nita_employer_cost = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employer_nita')
        rules_mapping[nita_employer_cost]['debit'] = nita_employer_expense
        rules_mapping[nita_employer_cost]['credit'] = paye_ni_payable

        nssf_employer_cost = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employer_nssf_employer')
        rules_mapping[nssf_employer_cost]['debit'] = nssf_employer_expense
        rules_mapping[nssf_employer_cost]['credit'] = pension_fund

        ahl_amount_employer = self.env.ref('l10n_ke_hr_payroll.l10n_ke_employer_salary_ahl_amount')
        rules_mapping[ahl_amount_employer]['debit'] = ahl_employer_expense
        rules_mapping[ahl_amount_employer]['credit'] = paye_ni_payable

        net = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_ke_hr_payroll.hr_payroll_structure_ken_employee_salary').id),
            ('code', '=', 'NET')
        ])
        rules_mapping[net]['credit'] = net_wages

        self._configure_payroll_account(
            companies,
            "KE",
            account_refs=[
                paye_ni_payable, net_wages, pension_fund, shif_payable, helb_payable, medical_insurance_payable,
                life_insurance_payable, education_insurance_payable, gross_salary, nssf_employer_expense,
                ahl_employer_expense, nita_employer_expense,
            ],
            rules_mapping=rules_mapping,
            default_account=gross_salary
        )
