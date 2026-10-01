from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mt', 'account.return.type')
    def _get_mt_account_return_type(self):
        return {
            'l10n_mt_reports.mt_tax_return_type': {
                'tax_payable_account_id': 'mt_3207',
                'tax_receivable_account_id': 'mt_2206',
            },
        }
