from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('hr', 'account.return.type')
    def _get_hr_account_return_type(self):
        return {
            'l10n_hr_reports.hr_tax_return_type': {
                'tax_payable_account_id': 'hr_226000',
                'tax_receivable_account_id': 'hr_158000',
            },
        }
