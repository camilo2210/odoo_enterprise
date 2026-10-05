from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cz', 'account.tax')
    def _get_cz_control_statement_account_tax(self):
        return self._parse_csv('cz', 'account.tax', module='l10n_cz_reports')

    @template('cz', 'account.return.type')
    def _get_cz_account_return_type(self):
        return {
            'l10n_cz_reports.cz_tax_return_type': {
                'tax_payable_account_id': 'chart_cz_343002',
                'tax_receivable_account_id': 'chart_cz_343001',
            },
            'l10n_cz_reports.cz_vat_control_statement_return_type': {
                'tax_payable_account_id': 'chart_cz_343002',
                'tax_receivable_account_id': 'chart_cz_343001',
            },
        }
