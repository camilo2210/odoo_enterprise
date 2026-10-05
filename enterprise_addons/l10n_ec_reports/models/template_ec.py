from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ec', 'account.return.type')
    def _get_ec_account_return_type(self):
        return {
            'l10n_ec_reports.ec_103_tax_return_type': {
                'tax_payable_account_id': 'ec_profit_tax_deduction',
                'tax_receivable_account_id': 'ec_profit_tax_credit',
            },
            'l10n_ec_reports.ec_104_tax_return_type': {
                'tax_payable_account_id': 'ec_vat_tax_deduction',
                'tax_receivable_account_id': 'ec_vat_tax_credit',
            },
            'l10n_ec_reports.ec_104_withhold_tax_return_type': {
                'tax_payable_account_id': 'ec_vat_tax_deduction',
                'tax_receivable_account_id': 'ec_withhold_tax_credit',
            },
        }
