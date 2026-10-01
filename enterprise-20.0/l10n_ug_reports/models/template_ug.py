from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ug', 'account.return.type')
    def _get_ug_account_return_type(self):
        return {
            'l10n_ug_reports.ug_tax_return_type': {
                'tax_payable_account_id': '411723',
                'tax_receivable_account_id': '3529',
            },
        }
