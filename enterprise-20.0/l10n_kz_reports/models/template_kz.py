from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('kz', 'account.return.type')
    def _get_kz_account_return_type(self):
        return {
            'l10n_kz_reports.kz_tax_return_type': {
                'tax_payable_account_id': 'kz3100',
                'tax_receivable_account_id': 'kz1400',
            },
        }
