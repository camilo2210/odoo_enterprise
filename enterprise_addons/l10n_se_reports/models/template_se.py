from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('se', 'account.return.type')
    def _get_se_account_return_type(self):
        return {
            'l10n_se_reports.se_tax_return_type': {
                'tax_payable_account_id': 'a2650',
                'tax_receivable_account_id': 'a1650',
            },
        }

    @template('se_K2', 'account.return.type')
    def _get_se__2_account_return_type(self):
        return {
            'l10n_se_reports.se_tax_return_type': {
                'tax_payable_account_id': 'a2650',
                'tax_receivable_account_id': 'a1650',
            },
        }

    @template('se_K3', 'account.return.type')
    def _get_se__3_account_return_type(self):
        return {
            'l10n_se_reports.se_tax_return_type': {
                'tax_payable_account_id': 'a2650',
                'tax_receivable_account_id': 'a1650',
            },
        }
