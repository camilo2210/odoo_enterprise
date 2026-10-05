from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('es_common', 'account.return.type')
    def _get_es_common_account_return_type(self):
        return {
            'l10n_es_reports.es_mod303_tax_return_type': {
                'tax_payable_account_id': 'account_common_4750',
                'tax_receivable_account_id': 'account_common_4700',
            },
            'l10n_es_reports.es_mod111_tax_return_type': {
                'tax_payable_account_id': 'account_common_4750',
                'tax_receivable_account_id': 'account_common_4709',
            },
            'l10n_es_reports.es_mod115_tax_return_type': {
                'tax_payable_account_id': 'account_common_4750',
                'tax_receivable_account_id': 'account_common_4709',
            },
        }
