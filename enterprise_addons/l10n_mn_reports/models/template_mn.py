from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('mn', 'account.return.type')
    def _get_mn_account_return_type(self):
        return {
            'l10n_mn_reports.mn_corporate_tax_return_type': {
                'tax_payable_account_id': 'account_template_3401_9902',
                'tax_receivable_account_id': 'account_template_1204_9902',
            },
            'l10n_mn_reports.mn_tax_return_type': {
                'tax_payable_account_id': 'account_template_3401_9902',
                'tax_receivable_account_id': 'account_template_1204_9902',
            },
        }
