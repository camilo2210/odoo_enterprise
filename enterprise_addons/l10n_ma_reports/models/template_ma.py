from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ma', 'account.return.type')
    def _get_ma_account_return_type(self):
        return {
            'l10n_ma_reports.ma_tax_return_type': {
                'tax_payable_account_id': 'pcg_4456',
                'tax_receivable_account_id': 'pcg_3456',
            },
        }
