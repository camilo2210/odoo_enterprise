from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('bh', 'account.return.type')
    def _get_bh_account_return_type(self):
        return {
            'l10n_bh_reports.bh_full_tax_return_type': {
                'tax_payable_account_id': 'bh_account_200904',
                'tax_receivable_account_id': 'bh_account_200903',
            },
            'l10n_bh_reports.bh_simplified_tax_return_type': {
                'tax_payable_account_id': 'bh_account_200904',
                'tax_receivable_account_id': 'bh_account_200903',
            },
        }
