from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ee', 'account.return.type')
    def _get_ee_account_return_type(self):
        return {
            'l10n_ee_reports.ee_tax_return_type': {
                'tax_payable_account_id': 'l10n_ee_201200',
                'tax_receivable_account_id': 'l10n_ee_201205',
            },
        }
