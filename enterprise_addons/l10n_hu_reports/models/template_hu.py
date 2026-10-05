from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('hu', 'account.return.type')
    def _get_hu_account_return_type(self):
        return {
            'l10n_hu_reports.hu_tax_return_type': {
                'tax_payable_account_id': 'l10n_hu_468',
                'tax_receivable_account_id': 'l10n_hu_4681',
            },
        }
