from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('de_skr03', 'res.company')
    def _get_de_skr03_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'account_0980',
                'deferred_revenue_account_id': 'account_0990',
            }
        }

    @template('de_skr04', 'res.company')
    def _get_de_skr04_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'chart_skr04_1900',
                'deferred_revenue_account_id': 'chart_skr04_3900',
            }
        }

    @template('de_skr03', 'account.return.type')
    def _get_de_skr03_account_return_type(self):
        return {
            'l10n_de_reports.de_tax_return_type': {
                'tax_payable_account_id': 'account_1797',
                'tax_receivable_account_id': 'account_1545',
                'advance_tax_payment_account_id': 'account_1780',
            },
        }

    @template('de_skr04', 'account.return.type')
    def _get_de_skr04_account_return_type(self):
        return {
            'l10n_de_reports.de_tax_return_type': {
                'tax_payable_account_id': 'chart_skr04_3860',
                'tax_receivable_account_id': 'chart_skr04_1421',
                'advance_tax_payment_account_id': 'chart_skr04_3820',
            },
        }
