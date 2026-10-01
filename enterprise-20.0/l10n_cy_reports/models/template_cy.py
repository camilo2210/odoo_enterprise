from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cy', 'account.return.type')
    def _get_cy_account_return_type(self):
        return {
            'l10n_cy_reports.cy_tax_return_type': {
                'tax_payable_account_id': 'cy_2200',
                'tax_receivable_account_id': 'cy_2205',
            },
        }
