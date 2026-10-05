from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('us', 'res.company')
    def _get_us_reports_res_company(self):
        return {
            self.env.company.id: {
                'account_reports_negative_format': 'parentheses',
                'deferred_expense_account_id': 'account_account_us_prepaid_expenses',
                'deferred_revenue_account_id': 'account_account_us_deferred_revenue',
            },
        }

    @template('us', 'account.return.type')
    def _get_us_account_return_type(self):
        return {
            'l10n_us_reports.tax_return_type': {
                'tax_payable_account_id': 'account_account_us_tax_payable',
                'tax_receivable_account_id': 'account_account_us_tax_receivable',
            },
        }
