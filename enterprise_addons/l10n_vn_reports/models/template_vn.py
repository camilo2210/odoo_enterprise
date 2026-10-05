from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('vn', 'account.return.type')
    def _get_vn_account_return_type(self):
        return {
            'l10n_vn_reports.vn_tax_return_type': {
                'tax_payable_account_id': 'chart3331',
                'tax_receivable_account_id': 'chart133',
            },
        }
