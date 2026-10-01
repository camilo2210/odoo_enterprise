from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('tr', 'account.return.type')
    def _get_tr_account_return_type(self):
        return {
            'l10n_tr_reports.tr_stamp_tax_return_type': {
                'tax_payable_account_id': 'tr360',
                'tax_receivable_account_id': 'tr193',
            },
            'l10n_tr_reports.tr_tax_return_type': {
                'tax_payable_account_id': 'tr360',
                'tax_receivable_account_id': 'tr193',
            },
        }
