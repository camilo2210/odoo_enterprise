from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mu', 'account.return.type')
    def _get_mu_account_return_type(self):
        return {
            'l10n_mu_reports.mu_tax_return_type': {
                'tax_payable_account_id': 'mu_tax_payable',
                'tax_receivable_account_id': 'mu_tax_receivable',
            },
        }
