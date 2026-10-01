from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('zm', 'account.return.type')
    def _get_zm_account_return_type(self):
        return {
            'l10n_zm_reports.zm_tax_return_type': {
                'tax_payable_account_id': 'zm_account_9520000',
                'tax_receivable_account_id': 'zm_account_8310000',
            },
        }
