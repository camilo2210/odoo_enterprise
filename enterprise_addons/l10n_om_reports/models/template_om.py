from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('om', 'account.return.type')
    def _get_om_account_return_type(self):
        return {
            'l10n_om_reports.om_tax_return_type': {
                'tax_payable_account_id': 'om_account_200904',
                'tax_receivable_account_id': 'om_account_200903',
            },
        }
