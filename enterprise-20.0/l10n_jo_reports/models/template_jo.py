from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('jo_standard', 'account.return.type')
    def _get_jo_standard_account_return_type(self):
        return {
            'l10n_jo_reports.jo_tax_return_type': {
                'tax_payable_account_id': 'jo_account_200905',
                'tax_receivable_account_id': 'jo_account_200906',
            },
        }
