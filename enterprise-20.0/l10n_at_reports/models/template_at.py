from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('at', 'account.return.type')
    def _get_at_account_return_type(self):
        return {
            'l10n_at_reports.at_tax_return_type': {
                'tax_payable_account_id': 'chart_at_template_3530',
                'tax_receivable_account_id': 'chart_at_template_3531',
            },
        }
