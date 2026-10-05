from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('kr', 'account.return.type')
    def _get_kr_account_return_type(self):
        return {
            'l10n_kr_reports.kr_tax_return_type': {
                'tax_payable_account_id': 'l10n_kr_210970',
                'tax_receivable_account_id': 'l10n_kr_104960',
            },
            'l10n_kr_reports.kr_simplified_tax_return_type': {
                'tax_payable_account_id': 'l10n_kr_210970',
                'tax_receivable_account_id': 'l10n_kr_104960',
            },
        }
