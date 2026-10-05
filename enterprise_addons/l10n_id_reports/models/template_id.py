from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('id', 'account.return.type')
    def _get_id_account_return_type(self):
        return {
            'l10n_id_reports.id_vat_return_type': {
                'tax_payable_account_id': 'l10n_id_21100011',
                'tax_receivable_account_id': 'l10n_id_11210012',
            },
        }
