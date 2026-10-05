from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ca_2023', 'account.return.type')
    def _get_ca_2023_account_return_type(self):
        return {
            'l10n_ca_reports.ca_gsthst_tax_return_type': {
                'tax_payable_account_id': 'l10n_ca_gsthst_payable',
                'tax_receivable_account_id': 'l10n_ca_gsthst_receivable',
            },
            'l10n_ca_reports.ca_qst_tax_return_type': {
                'tax_payable_account_id': 'l10n_ca_qst_payable',
                'tax_receivable_account_id': 'l10n_ca_qst_receivable',
            },
            'l10n_ca_reports.ca_pst_bc_tax_return_type': {
                'tax_payable_account_id': 'l10n_ca_pst_payable',
                'tax_receivable_account_id': 'l10n_ca_pst_receivable',
            },
            'l10n_ca_reports.ca_pst_mb_tax_return_type': {
                'tax_payable_account_id': 'l10n_ca_pst_payable',
                'tax_receivable_account_id': 'l10n_ca_pst_receivable',
            },
            'l10n_ca_reports.ca_pst_sk_tax_return_type': {
                'tax_payable_account_id': 'l10n_ca_pst_payable',
                'tax_receivable_account_id': 'l10n_ca_pst_receivable',
            },
        }
