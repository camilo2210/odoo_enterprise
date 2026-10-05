from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('it', 'account.return.type')
    def _get_it_account_return_type(self):
        return {
            'l10n_it_reports.it_tax_return_type': {
                'tax_payable_account_id': '2605',
                'tax_receivable_account_id': '26051',
            },
            'l10n_it_reports.it_withh_tax_return_type': {
                'tax_payable_account_id': '2611',
                'tax_receivable_account_id': '26111',
            },
            'l10n_it_reports.it_enasarco_tax_return_type': {
                'tax_payable_account_id': '2610',
                'tax_receivable_account_id': '26101',
            },
        }
