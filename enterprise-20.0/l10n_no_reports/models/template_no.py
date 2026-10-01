from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('no', 'account.return.type')
    def _get_no_account_return_type(self):
        return {
            'l10n_no_reports.no_tax_return_type': {
                'tax_payable_account_id': 'chart2740',
                'tax_receivable_account_id': 'chart2741',
            },
        }
