from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ch', 'account.return.type')
    def _get_ch_account_return_type(self):
        return {
            'l10n_ch_reports.ch_tax_return_type': {
                'tax_payable_account_id': 'ch_coa_2201',
                'tax_receivable_account_id': 'ch_coa_1176',
            },
        }
