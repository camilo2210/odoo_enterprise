from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cl', 'account.return.type')
    def _get_cl_account_return_type(self):
        return {
            'l10n_cl_reports.cl_f29_tax_return_type': {
                'tax_payable_account_id': 'account_210760',
                'tax_receivable_account_id': 'account_110720',
            },
        }
