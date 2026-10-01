from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('pt', 'account.return.type')
    def _get_pt_account_return_type(self):
        return {
            'l10n_pt_reports.pt_tax_return_type': {
                'tax_payable_account_id': 'chart_2436',
                'tax_receivable_account_id': 'chart_2437',
            },
        }
