# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_mx(self, companies):
        employment_subsidy = 'cuenta110_01'
        employee_reimbursement = 'cuenta201_01_02'
        other_credits_fonacot = 'cuenta205_06_02'
        provision_wages = 'cuenta210_01'
        provision_vacation = 'cuenta210_02'
        provision_bonus = 'cuenta210_03'
        provision_savings_fund = 'cuenta210_04'
        provision_employer_imss = 'cuenta211_01'
        provision_sar = 'cuenta211_02'
        provision_infonavit = 'cuenta211_03'
        isr_income_taxes = 'cuenta216_01'
        imss_withholding_workers = 'cuenta216_11'

        wages_salaries = 'cuenta601_01'
        vacations = 'cuenta601_06'
        holiday_bonus_expense = 'cuenta601_07'
        bonus_expense = 'cuenta601_12'
        pantry = 'cuenta601_15'
        transport_support = 'cuenta601_16'
        transport_gasoline = 'cuenta601_16_02'
        savings_fund_expense = 'cuenta601_19'
        imss_quota = 'cuenta601_26'
        contrib_infonavit = 'cuenta601_27'
        contrib_sar = 'cuenta601_28'
        commissions_sales = 'cuenta601_74'

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #          MX Regular Pay Payroll Structure        #
        # ================================================ #

        gross_without_holidays = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_bruto')
        rules_mapping[gross_without_holidays]['debit'] = wages_salaries

        holidays_on_time = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_holidays_on_time')
        rules_mapping[holidays_on_time]['debit'] = provision_vacation

        gasoline_period = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_gasoline_period')
        rules_mapping[gasoline_period]['debit'] = transport_gasoline

        transport_period = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_transport_period')
        rules_mapping[transport_period]['debit'] = transport_support

        meal_voucher_period = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_meal_voucher_period')
        rules_mapping[meal_voucher_period]['debit'] = pantry

        holiday_bonus = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_holiday_bonus')
        rules_mapping[holiday_bonus]['debit'] = provision_vacation

        for xml_id in [
            'l10n_mx_regular_pay_discount_for_absence',
            'l10n_mx_regular_pay_imss_disabilities',
        ]:
            rule = self.env.ref(f'l10n_mx_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = wages_salaries

        savings_fund_employer_alw = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_employer_savings_fund_alw')
        rules_mapping[savings_fund_employer_alw]['debit'] = savings_fund_expense

        for xml_id in [
            'l10n_mx_hr_payroll_structure_mx_employee_salary_reimbursement_salary_rule',
            'l10n_mx_regular_pay_expenses',
        ]:
            rule = self.env.ref(f'l10n_mx_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = employee_reimbursement

        commissions = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_commissions')
        rules_mapping[commissions]['debit'] = commissions_sales

        bonus = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_bonus')
        rules_mapping[bonus]['debit'] = wages_salaries

        for xml_id in [
            'l10n_mx_regular_pay_isr',
            'l10n_mx_regular_pay_isr_holiday_bonus_tax',
        ]:
            rule = self.env.ref(f'l10n_mx_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = isr_income_taxes

        for xml_id in [
            'l10n_mx_regular_pay_savings_fund',
            'l10n_mx_regular_pay_employer_savings_fund',
        ]:
            rule = self.env.ref(f'l10n_mx_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = provision_savings_fund

        subsidy = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_subsidy')
        rules_mapping[subsidy]['debit'] = employment_subsidy

        infonavit = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_infonavit_employee')
        rules_mapping[infonavit]['debit'] = provision_infonavit

        fonacot = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_fonacot')
        rules_mapping[fonacot]['debit'] = other_credits_fonacot

        imss_employee = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_social_security_total_employee')
        rules_mapping[imss_employee]['credit'] = imss_withholding_workers

        for xml_id in [
            'l10n_mx_regular_pay_imss_work_risk',
            'l10n_mx_regular_pay_imss_disease_maternity_fixed',
            'l10n_mx_regular_pay_imss_disease_maternity_additional',
            'l10n_mx_regular_pay_imss_disease_maternity_medical',
            'l10n_mx_regular_pay_imss_disease_maternity_money',
            'l10n_mx_regular_pay_imss_disability_life',
        ]:
            rule = self.env.ref(f'l10n_mx_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = imss_quota
            rules_mapping[rule]['credit'] = provision_employer_imss

        for xml_id in [
            'l10n_mx_regular_pay_imss_retirement',
            'l10n_mx_regular_pay_imss_ceav',
        ]:
            rule = self.env.ref(f'l10n_mx_hr_payroll.{xml_id}')
            rules_mapping[rule]['debit'] = contrib_sar
            rules_mapping[rule]['credit'] = provision_sar

        imss_nursery_employer = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_imss_nursery')
        rules_mapping[imss_nursery_employer]['debit'] = imss_quota
        rules_mapping[imss_nursery_employer]['credit'] = provision_employer_imss

        imss_infonavit_employer = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_infonavit')
        rules_mapping[imss_infonavit_employer]['debit'] = contrib_infonavit
        rules_mapping[imss_infonavit_employer]['credit'] = provision_infonavit

        provision_period_christmas = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_period_provisions_christmas_bonus')
        rules_mapping[provision_period_christmas]['debit'] = bonus_expense
        rules_mapping[provision_period_christmas]['credit'] = provision_bonus

        provision_period_holiday = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_period_provisions_holiday_bonus')
        rules_mapping[provision_period_holiday]['debit'] = holiday_bonus_expense
        rules_mapping[provision_period_holiday]['credit'] = provision_vacation

        provision_period_vacation = self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay_period_provisions_vacations_bonus')
        rules_mapping[provision_period_vacation]['debit'] = vacations
        rules_mapping[provision_period_vacation]['credit'] = provision_vacation

        net = self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.env.ref('l10n_mx_hr_payroll.l10n_mx_regular_pay').id),
            ('code', '=', 'NET')
        ])
        rules_mapping[net]['credit'] = provision_wages

        # ================================================ #
        #        MX Christmas Bonus Payroll Structure      #
        # ================================================ #

        basic = self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus_basic')
        rules_mapping[basic]['debit'] = provision_bonus

        isr = self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus_isr')
        rules_mapping[isr]['debit'] = isr_income_taxes

        net = self.env.ref('l10n_mx_hr_payroll.l10n_mx_christmas_bonus_net')
        rules_mapping[net]['credit'] = provision_wages

        self._configure_payroll_account(
            companies,
            "MX",
            account_refs=[
                employment_subsidy, employee_reimbursement, other_credits_fonacot, provision_wages, provision_vacation,
                provision_bonus, provision_savings_fund, provision_employer_imss, provision_sar, provision_infonavit,
                isr_income_taxes, imss_withholding_workers, wages_salaries, vacations, holiday_bonus_expense,
                bonus_expense, pantry, transport_support, transport_gasoline, savings_fund_expense, imss_quota,
                contrib_infonavit, contrib_sar, commissions_sales
            ],
            rules_mapping=rules_mapping,
            default_account=provision_wages
        )
