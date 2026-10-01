# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('bg', 'account.tax')
    def _get_bg_saft_account_tax(self):
        return self._parse_csv('bg', 'account.tax', module='l10n_bg_saft')

    @template('bg', 'account.account')
    def _get_bg_saft_account_code(self):
        company = self.env.company

        def update_account_code(account_code, saft_code):
            accounts = self.env['account.account'].with_company(company).search([
                *self.env['account.account']._check_company_domain(company),
                ('code', '=like', account_code),
                ('l10n_bg_saft_account_code', '=', False),
            ])
            for account in accounts:
                account.l10n_bg_saft_account_code = saft_code

        if company.bank_account_code_prefix:
            update_account_code(company.bank_account_code_prefix + "%", '503')
        if company.cash_account_code_prefix:
            update_account_code(company.cash_account_code_prefix + "%", '501')
        if company.transfer_account_code_prefix:
            update_account_code(company.transfer_account_code_prefix + "%", '434')
        if company.default_cash_difference_expense_account_id:
            update_account_code(company.default_cash_difference_expense_account_id.code, '443')
        if company.default_cash_difference_income_account_id:
            update_account_code(company.default_cash_difference_income_account_id.code, '443')
        if company.account_journal_early_pay_discount_gain_account_id:
            update_account_code(company.account_journal_early_pay_discount_gain_account_id.code, '729')
        if company.account_journal_early_pay_discount_loss_account_id:
            update_account_code(company.account_journal_early_pay_discount_loss_account_id.code, '623')

        return self._parse_csv('bg', 'account.account', module='l10n_bg_saft')
