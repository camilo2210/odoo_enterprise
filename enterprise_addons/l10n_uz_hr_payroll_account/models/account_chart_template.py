# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_uz(self, companies):
        """
        Payroll accounting mappings according to National Accounting
        Standard of Uzbekistan No. 21 (BHMS 21 / 21-sonli BHMS): "Chart of Accounts
        for Financial and Economic Activities of Enterprises" (Lex.uz Order No. 3593).
        https://lex.uz/uz/docs/-7282737#
        """
        # Chart of Accounts Template XML References
        wages_payable = 'uz6710'                  # Wages & Salaries Payable - Ish haqi bo'yicha xodimlar bilan hisob-kitoblar (6710)
        taxes_payable = 'uz6410'                  # Taxes & Duties Payable - Budjetga to'lovlar bo'yicha qarzlar (6410)
        pension_state_payable = 'uz6520'          # State Fund Contributions Payable - Davlat maqsadli jamg'armalariga to'lovlar (6520)
        pension_inps_payable = 'uz6530'           # Individual Pension Fund Contributions Payable - Yakka tartibdagi jamg'arma pensiya hisobvarag'i (6530)
        expense_claims_payable = 'uz6970'         # Employee Expense Claims Payable - Xodimlarga boshqa operatsiyalar bo'yicha qarzlar (6970)
        salaries_allowances_expense = 'uz9421'    # Salaries, Allowances & Bonus - Mehnatga haq to'lash xarajatlari (9421)
        leave_comp_expense = 'uz9422'             # Unused Leave Days Compensation Expense -Ishlatilmagan mehnat ta'tili kompensatsiyasi xarajatlari (9422)
        social_tax_expense = 'uz9423'             # Employer Social Tax Expense - Yagona ijtimoiy to'lov xarajatlari (9423)
        severance_pay_expense = 'uz9424'          # Severance Pay Expense - Ishdan bo'shatishda to'lanadigan nafaqa xarajatlari (9424)

        rules_mapping = defaultdict(dict)

        # ================================================ #
        #           UZ Employee Payroll Structure          #
        # ================================================ #

        # Basic Salary
        basic_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_basic_salary', raise_if_not_found=False) \
            or self.env['hr.salary.rule'].search([('code', '=', 'UZ_BASIC')], limit=1)
        if basic_rule:
            rules_mapping[basic_rule]['debit'] = salaries_allowances_expense

        # Seniority Supplement
        seniority_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_seniority_supplement', raise_if_not_found=False)
        if seniority_rule:
            rules_mapping[seniority_rule]['debit'] = salaries_allowances_expense

        # Bonus
        bonus_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_bonus', raise_if_not_found=False)
        if bonus_rule:
            rules_mapping[bonus_rule]['debit'] = salaries_allowances_expense

        # Other Allowance
        other_allowance_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_other_allowance', raise_if_not_found=False)
        if other_allowance_rule:
            rules_mapping[other_allowance_rule]['debit'] = salaries_allowances_expense

        # Remaining Leave Compensation
        leave_comp_rule = self.env.ref('l10n_uz_hr_payroll.hr_rule_remaining_leave_compensation', raise_if_not_found=False)
        if leave_comp_rule:
            rules_mapping[leave_comp_rule]['debit'] = leave_comp_expense

        # Employer Social Tax
        social_tax_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_social_tax_employer_contribution', raise_if_not_found=False)
        if social_tax_rule:
            rules_mapping[social_tax_rule]['debit'] = social_tax_expense
            rules_mapping[social_tax_rule]['credit'] = pension_state_payable

        # Pension Fund (INPS)
        pension_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_pension_fund', raise_if_not_found=False)
        if pension_rule:
            rules_mapping[pension_rule]['debit'] = taxes_payable
            rules_mapping[pension_rule]['credit'] = pension_inps_payable

        # Severance Payment
        severance_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_severance_pay', raise_if_not_found=False)
        if severance_rule:
            rules_mapping[severance_rule]['debit'] = severance_pay_expense

        # Personal Income Tax (PIT)
        income_tax_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_personal_income_tax', raise_if_not_found=False)
        if income_tax_rule:
            rules_mapping[income_tax_rule]['debit'] = taxes_payable

        # Expense Reimbursement
        expense_reimb_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_expense_reimbursement', raise_if_not_found=False)
        if expense_reimb_rule:
            rules_mapping[expense_reimb_rule]['debit'] = expense_claims_payable

        # Net Salary
        net_rule = self.env.ref('l10n_uz_hr_payroll.l10n_uz_monthly_pay_net', raise_if_not_found=False) \
            or self.env['hr.salary.rule'].search([('code', '=', 'NET')], limit=1)
        if net_rule:
            rules_mapping[net_rule]['credit'] = wages_payable

        self._configure_payroll_account(
            companies,
            "UZ",
            account_refs=[
                wages_payable,
                taxes_payable,
                pension_state_payable,
                pension_inps_payable,
                expense_claims_payable,
                salaries_allowances_expense,
                leave_comp_expense,
                social_tax_expense,
                severance_pay_expense,
            ],
            rules_mapping=rules_mapping,
            default_account=wages_payable
        )
