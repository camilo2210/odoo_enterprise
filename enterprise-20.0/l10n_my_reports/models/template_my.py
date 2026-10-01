from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('my', 'account.return.type')
    def _get_my_account_return_type(self):
        return {
            'l10n_my_reports.my_tax_return_type_sst_02_a_b': {
                'tax_payable_account_id': 'l10n_my_440700',
                'tax_receivable_account_id': 'l10n_my_230300',
            },
        }
