from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('th', 'account.return.type')
    def _get_th_account_return_type(self):
        return {
            'l10n_th_reports.th_tax_return_type': {
                'tax_payable_account_id': 'l10n_th_account_213400',
                'tax_receivable_account_id': 'l10n_th_account_114400',
            },
        }
