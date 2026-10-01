from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('bg', 'account.return.type')
    def _get_bg_account_return_type(self):
        return {
            'l10n_bg_reports.bg_tax_return_type': {
                'tax_payable_account_id': 'l10n_bg_4539',
                'tax_receivable_account_id': 'l10n_bg_4538',
            },
        }
