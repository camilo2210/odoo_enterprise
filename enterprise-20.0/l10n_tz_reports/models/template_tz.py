from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('tz', 'account.return.type')
    def _get_tz_account_return_type(self):
        return {
            'l10n_tz_reports.tz_tax_return_type': {
                'tax_payable_account_id': 'tz_308',
                'tax_receivable_account_id': 'tz_108',
            },
        }
