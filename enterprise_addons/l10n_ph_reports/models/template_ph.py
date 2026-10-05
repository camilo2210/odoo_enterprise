from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ph', 'account.return.type')
    def _get_ph_account_return_type(self):
        return {
            'l10n_ph_reports.ph_tax_return_type': {
                'tax_payable_account_id': 'l10n_ph_account_202010',
                'tax_receivable_account_id': 'l10n_ph_account_103040',
            },
            'l10n_ph_reports.ph_wht_tax_return_type': {
                'tax_payable_account_id': 'l10n_ph_account_202020',
                'tax_receivable_account_id': 'l10n_ph_account_103050',
            },
            'l10n_ph_reports.ph_percentage_tax_return_type': {
                'tax_payable_account_id': 'l10n_ph_account_202030',
                'tax_receivable_account_id': 'l10n_ph_account_103030',
            },
        }
