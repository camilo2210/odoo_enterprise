from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ae', 'res.company')
    def _get_ae_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'uae_account_128000',
                'deferred_revenue_account_id': 'uae_account_212000',
            }
        }

    @template('ae', 'account.return.type')
    def _get_ae_account_return_type(self):
        return {
            'l10n_ae_reports.ae_tax_return_type': {
                'tax_payable_account_id': 'uae_account_230200',
                'tax_receivable_account_id': 'uae_account_151000',
            },
        }
