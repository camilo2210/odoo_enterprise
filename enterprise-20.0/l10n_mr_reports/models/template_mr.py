from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mr', 'account.return.type')
    def _get_mr_account_return_type(self):
        return {
            'l10n_mr_reports.mr_tax_return_type': {
                'tax_payable_account_id': 'mr_43551',
                'tax_receivable_account_id': 'mr_435671',
            },
        }
