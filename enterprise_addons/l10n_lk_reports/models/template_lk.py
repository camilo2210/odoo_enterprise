from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('lk', 'account.return.type')
    def _get_lk_account_return_type(self):
        return {
            'l10n_lk_reports.lk_vat_return_type': {
                'tax_payable_account_id': 'l10n_lk_230200',
                'tax_receivable_account_id': 'l10n_lk_180300',
            },
        }
