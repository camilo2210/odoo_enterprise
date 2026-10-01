from odoo import models
from odoo.addons.account.models.chart_template import template
from odoo.addons.account_loans import _account_loans_import_loan_demo


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template('generic_coa', model='account.journal', demo=True)
    def _get_demo_data_loan_journal(self):
        return {
            'account_loans_journal_loan': {
                'name': self.env._("Journal Loan Demo"),
                'type': 'general',
                'code': 'LOAN',
            },
        }

    @template('generic_coa', model='account.loan', demo=True)
    def _get_demo_data_loan(self):
        return {
            'account_loans_loan_demo1': {
                'name': self.env._("Loan Demo 1"),
                'asset_group_id': 'account_asset_group_demo',
                'journal_id': 'account_loans_journal_loan',
                'long_term_account_id': 'non_current_assets',
                'short_term_account_id': 'current_liabilities',
                'expense_account_id': 'expense',
            },
            'account_loans_loan_demo2': {
                'name': self.env._("Loan Demo 2"),
                'asset_group_id': 'account_asset_group_demo',
                'journal_id': 'account_loans_journal_loan',
                'long_term_account_id': 'non_current_assets',
                'short_term_account_id': 'current_liabilities',
                'expense_account_id': 'expense',
            },
        }

    def _post_load_demo_data(self, template_code):

        if template_code == "generic_coa":
            _account_loans_import_loan_demo(
                self.env,
                self.ref('account_loans_loan_demo1'),
                self.env.ref('account_loans.account_loans_loan_demo_file_csv')
            )

            _account_loans_import_loan_demo(
                self.env,
                self.ref('account_loans_loan_demo2'),
                self.env.ref('account_loans.account_loans_loan_demo_file_xlsx')
            )
        return super()._post_load_demo_data(template_code)
