from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ng', 'account.return.type')
    def _get_ng_account_return_type(self):
        return {
            'l10n_ng_reports.ng_tax_return_type': {
                'tax_payable_account_id': 'l10n_ng_tax_payable',
                'tax_receivable_account_id': 'l10n_ng_tax_receivable',
            },
            'l10n_ng_reports.ng_wh_vat_return_type': {
                'tax_payable_account_id': 'l10n_ng_withholding_payable',
                'tax_receivable_account_id': 'l10n_ng_withholding_receivable',
            },
        }
