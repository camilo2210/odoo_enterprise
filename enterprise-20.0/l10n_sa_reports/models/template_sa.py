from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('sa', 'account.return.type')
    def _get_sa_account_return_type(self):
        return {
            'l10n_sa_reports.sa_tax_return_type': {
                'tax_payable_account_id': 'sa_account_202003',
                'tax_receivable_account_id': 'sa_account_100103',
            },
            'l10n_sa_reports.sa_withh_tax_return_type': {
                'tax_payable_account_id': 'sa_account_202003',
                'tax_receivable_account_id': 'sa_account_102010',
            },
        }
