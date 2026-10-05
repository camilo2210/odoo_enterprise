from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('lu', 'res.company')
    def _get_lu_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'lu_2011_account_481',
                'deferred_revenue_account_id': 'lu_2011_account_482',
            }
        }

    @template('lu', 'account.return.type')
    def _get_lu_account_return_type(self):
        return {
            'l10n_lu_reports.lu_annual_statement_return_type': {
                'tax_payable_account_id': 'lu_2011_account_461412',
                'tax_receivable_account_id': 'lu_2011_account_421612',
            },
            'l10n_lu_reports.lu_tax_return_type': {
                'tax_payable_account_id': 'lu_2011_account_461412',
                'tax_receivable_account_id': 'lu_2011_account_421612',
                'advance_tax_payment_account_id': 'lu_2011_account_421613',
            },
        }
