from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('in', 'account.return.type')
    def _get_in_account_return_type(self):
        return {
            'l10n_in_reports.in_gstr1_return_type': {
                'tax_payable_account_id': 'p11239',
                'tax_receivable_account_id': 'p10059',
            },
            'l10n_in_reports.in_gstr2b_return_type': {
                'tax_payable_account_id': 'p11239',
                'tax_receivable_account_id': 'p10059',
            },
        }
