from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('tw', 'account.return.type')
    def _get_tw_account_return_type(self):
        return {
            'l10n_tw_reports.tw_tax_return_type': {
                'tax_payable_account_id': 'l10n_tw_account_2285',
                'tax_receivable_account_id': 'l10n_tw_account_1486',
            },
            'l10n_tw_reports.tw_403_tax_return_type': {
                'tax_payable_account_id': 'l10n_tw_account_2285',
                'tax_receivable_account_id': 'l10n_tw_account_1486',
            },
            'l10n_tw_reports.tw_404_tax_return_type': {
                'tax_payable_account_id': 'l10n_tw_account_2287',
                'tax_receivable_account_id': 'l10n_tw_account_1487',
            },
        }
