from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('nl', 'account.return.type')
    def _get_nl_account_return_type(self):
        return {
            'l10n_nl_reports.nl_tax_correction_return_type': {
                'tax_payable_account_id': 'vat_tax_liabilities',
                'tax_receivable_account_id': 'vat_tax_assets',
            },
            'l10n_nl_reports.nl_tax_return_type': {
                'tax_payable_account_id': 'vat_tax_liabilities',
                'tax_receivable_account_id': 'vat_tax_assets',
            },
        }
