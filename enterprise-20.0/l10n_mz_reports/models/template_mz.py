from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mz', 'account.return.type')
    def _get_mz_account_return_type(self):
        return {
            'l10n_mz_reports.mz_tax_return_type': {
                'tax_payable_account_id': 'l10n_mz_account_4437',
                'tax_receivable_account_id': 'l10n_mz_account_4438',
            },
        }
