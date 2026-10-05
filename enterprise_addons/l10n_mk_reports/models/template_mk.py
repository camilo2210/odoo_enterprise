from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mk', 'account.return.type')
    def _get_mk_account_return_type(self):
        return {
            'l10n_mk_reports.mk_tax_return_type': {
                'tax_payable_account_id': 'l10n_mk_account_210',
                'tax_receivable_account_id': 'l10n_mk_account_110',
            },
        }
