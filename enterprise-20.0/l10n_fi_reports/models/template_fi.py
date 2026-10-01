from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('fi', 'account.return.type')
    def _get_fi_account_return_type(self):
        return {
            'l10n_fi_reports.fi_tax_return_type': {
                'tax_payable_account_id': 'account_2939',
                'tax_receivable_account_id': 'account_1764',
            },
        }
