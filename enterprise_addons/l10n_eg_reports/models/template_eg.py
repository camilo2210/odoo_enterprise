from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('eg', 'account.return.type')
    def _get_eg_account_return_type(self):
        return {
            'l10n_eg_reports.eg_tax_return_type': {
                'tax_payable_account_id': 'egy_account_220600',
                'tax_receivable_account_id': 'egy_account_151000',
            },
            'l10n_eg_reports.eg_withholding_tax_return_type': {
                'tax_payable_account_id': 'egy_account_220600',
                'tax_receivable_account_id': 'egy_account_151000',
            },
        }
