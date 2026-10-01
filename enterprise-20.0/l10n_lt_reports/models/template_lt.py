from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('lt', 'account.return.type')
    def _get_lt_account_return_type(self):
        return {
            'l10n_lt_reports.lt_tax_return_type': {
                'tax_payable_account_id': 'account_account_template_44921',
                'tax_receivable_account_id': 'account_account_template_24411',
            },
        }
