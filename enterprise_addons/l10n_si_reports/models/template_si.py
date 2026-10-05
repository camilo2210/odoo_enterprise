from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('si', 'account.return.type')
    def _get_si_account_return_type(self):
        return {
            'l10n_si_reports.si_tax_return_type': {
                'tax_payable_account_id': 'gd_acc_260800',
                'tax_receivable_account_id': 'gd_acc_160800',
            },
        }
