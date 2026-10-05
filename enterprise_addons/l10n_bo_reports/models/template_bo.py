from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('bo', 'account.return.type')
    def _get_bo_account_return_type(self):
        return {
            'l10n_bo_reports.bo_tax_return_type': {
                'tax_payable_account_id': 'l10n_bo_21399',
                'tax_receivable_account_id': 'l10n_bo_1142',
                'advance_tax_payment_account_id': 'l10n_bo_1142',
            },
        }
