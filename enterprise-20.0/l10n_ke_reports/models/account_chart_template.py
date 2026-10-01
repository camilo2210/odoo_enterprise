from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ke', 'res.company')
    def _get_ke_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'ke120011',
                'deferred_revenue_account_id': 'ke211000',
            }
        }

    @template('ke', 'account.return.type')
    def _get_ke_account_return_type(self):
        return {
            'l10n_ke_reports.ke_tax_return_type': {
                'tax_payable_account_id': 'ke2201',
                'tax_receivable_account_id': 'ke1111',
            },
            'l10n_ke_reports.ke_wh_tax_return_type': {
                'tax_payable_account_id': 'ke2201',
                'tax_receivable_account_id': 'ke1111',
            },
        }
