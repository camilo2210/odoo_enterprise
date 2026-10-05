from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('au', 'res.company')
    def _get_au_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'au_12200',
                'deferred_revenue_account_id': 'au_21760',
            }
        }

    @template('au', 'account.return.type')
    def _get_au_account_return_type(self):
        return {
            'l10n_au_reports.au_tax_bas_a_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_c_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_d_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_f_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_g_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_u_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_v_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_w_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_x_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
            'l10n_au_reports.au_tax_bas_y_return_type': {
                'tax_payable_account_id': 'au_21320',
                'tax_receivable_account_id': 'au_21321',
            },
        }
