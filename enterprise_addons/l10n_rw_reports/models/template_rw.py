from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('rw', 'account.return.type')
    def _get_rw_account_return_type(self):
        return {
            'l10n_rw_reports.rw_tax_return_type': {
                'tax_payable_account_id': 'rw_308',
                'tax_receivable_account_id': 'rw_108',
            },
        }
