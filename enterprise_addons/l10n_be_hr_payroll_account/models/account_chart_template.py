# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_be(self, companies):
        withholding_taxes = 'a453'
        onss = 'a454'
        due_amount_net = 'a455'
        other_social_obligations = 'a459'
        remuneration = 'a6202'
        onss_employer = 'a621'
        provision_horeca_employees = 'a6262'
        provision_horeca_workers = 'a6263'
        ip = 'a643'
        meal_vouchers = 'a743'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #              CP200: 13th month                   #
        # ================================================ #

        basic_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id),
            ('code', '=', 'BONUS_BASIC')
        ])
        rules_mapping[basic_rule]['credit'] = due_amount_net

        onss_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_bonus_social_contributions')
        rules_mapping[onss_rule]['credit'] = onss

        pp_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_cct90_p_p')
        rules_mapping[pp_rule]['credit'] = withholding_taxes

        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id),
            ('code', '=', 'NET')
        ])
        rules_mapping[net_rule]['credit'] = due_amount_net

        # ================================================ #
        #         CP200: Employees Monthly Pay             #
        # ================================================ #

        # Remunerations
        remun_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_remuneration')
        rules_mapping[remun_rule]['debit'] = remuneration

        # IP
        ip_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_ip')
        rules_mapping[ip_rule]['debit'] = ip

        # ONSS (Onss - employment bonus)
        onss_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_onss_total')
        rules_mapping[onss_rule]['credit'] = onss

        # Private car reimbursement
        car_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_private_car')
        rules_mapping[car_rule]['debit'] = remuneration

        # Total withholding taxes
        pp_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_withholding_taxes_total')
        rules_mapping[pp_rule]['credit'] = withholding_taxes

        # Special Social Contribution (MISC ONSS)
        monss_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_mis_ex_onss')
        rules_mapping[monss_rule]['debit'] = onss  # Note: this is a credit, but the amount is negative

        # Representation Fees
        rep_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_representation_fees')
        rules_mapping[rep_rule]['debit'] = remuneration

        # IP Deduction
        ip_ded_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_ip_deduction')
        rules_mapping[ip_ded_rule]['debit'] = withholding_taxes  # Note: This is a credit, but the amount is negative

        # Meal vouchers
        meal_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_ch_worker')
        rules_mapping[meal_rule]['debit'] = meal_vouchers  # Note: this is a credit, but the amount is negative

        # Owed Remunerations (NET)
        net_rule = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id),
            ('code', '=', 'NET')
        ])
        rules_mapping[net_rule]['credit'] = due_amount_net

        # ONSS Employer
        onss_rule = self.env.ref('l10n_be_hr_payroll.l10n_be_employees_salary_onss_employer_total')
        rules_mapping[onss_rule]['debit'] = onss_employer
        rules_mapping[onss_rule]['credit'] = onss

        # Mobility Budget Withholding Tax
        net_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_mobility_budget_tax', raise_if_not_found=False)
        if net_rule:
            rules_mapping[net_rule]['credit'] = onss

        # ================================================ #
        #              CP200: Termination Holidays N       #
        # ================================================ #

        onss_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n_rules_onss_termination')
        rules_mapping[onss_rule]['credit'] = onss

        monss_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n_rules_special_contribution_termination')
        rules_mapping[monss_rule]['credit'] = onss

        pp_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n_rules_professional_tax_termination')
        rules_mapping[pp_rule]['credit'] = withholding_taxes

        # ================================================ #
        #        CP200: Termination Holidays N-1           #
        # ================================================ #

        basic_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n1_total_n')
        rules_mapping[basic_rule]['credit'] = due_amount_net

        # ================================================ #
        #         CP302: Employees Monthly Pay             #
        # ================================================ #

        pfa_contrib_rule_empl = self.env.ref('l10n_be_hr_payroll.cp302_employees_salary_thirteen_month_contribution_employee')
        pfa_contrib_rule_work = self.env.ref('l10n_be_hr_payroll.cp302_employees_salary_thirteen_month_contribution_worker')
        rules_mapping[pfa_contrib_rule_empl]['credit'] = other_social_obligations
        rules_mapping[pfa_contrib_rule_work]['credit'] = other_social_obligations
        rules_mapping[pfa_contrib_rule_empl]['debit'] = provision_horeca_employees
        rules_mapping[pfa_contrib_rule_work]['debit'] = provision_horeca_workers

        self._configure_payroll_account(
            companies,
            "BE",
            account_refs=[
                withholding_taxes, onss, due_amount_net, other_social_obligations, remuneration, onss_employer,
                provision_horeca_employees, provision_horeca_workers, ip, meal_vouchers
            ],
            rules_mapping=rules_mapping,
            default_account=remuneration
        )

    def _configure_payroll_account_be_comp(self, companies):
        return self._configure_payroll_account_be(companies)

    def _configure_payroll_account_be_asso(self, companies):
        return self._configure_payroll_account_be(companies)
