from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('jp', 'account.return.type')
    def _get_jp_account_return_type(self):
        return {
            'l10n_jp_reports.jp_jct_return_accumulation': {
                'tax_payable_account_id': 'l10n_jp_10B100660',
                'tax_receivable_account_id': 'l10n_jp_10A100690',
                'advance_tax_payment_account_id': 'l10n_jp_10A101152',
            },
            'l10n_jp_reports.jp_jct_return_deduction': {
                'tax_payable_account_id': 'l10n_jp_10B100660',
                'tax_receivable_account_id': 'l10n_jp_10A100690',
                'advance_tax_payment_account_id': 'l10n_jp_10A101152',
            },
        }
