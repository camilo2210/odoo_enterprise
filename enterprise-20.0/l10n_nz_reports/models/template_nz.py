from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('nz', 'account.return.type')
    def _get_nz_account_return_type(self):
        return {
            'l10n_nz_reports.nz_tax_return_type': {
                'tax_payable_account_id': 'nz_21320',
                'tax_receivable_account_id': 'nz_21321',
            },
        }
