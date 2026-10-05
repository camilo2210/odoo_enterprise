from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('lv', 'account.return.type')
    def _get_lv_account_return_type(self):
        return {
            'l10n_lv_reports.lv_tax_return_type': {
                'tax_payable_account_id': 'a57211',
                'tax_receivable_account_id': 'a2345',
            },
        }
