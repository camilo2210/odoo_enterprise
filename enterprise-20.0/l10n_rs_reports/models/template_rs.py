from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('rs', 'account.return.type')
    def _get_rs_account_return_type(self):
        return {
            'l10n_rs_reports.rs_tax_return_type': {
                'tax_payable_account_id': 'rs_479',
                'tax_receivable_account_id': 'rs_279',
            },
        }
