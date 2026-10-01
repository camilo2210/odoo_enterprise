from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('sk', 'account.return.type')
    def _get_sk_account_return_type(self):
        return {
            'l10n_sk_reports.sk_tax_return_type': {
                'tax_payable_account_id': 'chart_sk_343900',
                'tax_receivable_account_id': 'chart_sk_343910',
            },
            'l10n_sk_reports.sk_vat_control_statement_return_type': {
                'tax_payable_account_id': 'chart_sk_343900',
                'tax_receivable_account_id': 'chart_sk_343910',
            },
        }
