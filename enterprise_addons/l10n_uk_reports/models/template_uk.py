from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('uk', 'account.return.type')
    def _get_uk_account_return_type(self):
        return {
            'l10n_uk_reports.uk_tax_return_type': {
                'tax_payable_account_id': '220200',
                'tax_receivable_account_id': '220202',
            },
        }
