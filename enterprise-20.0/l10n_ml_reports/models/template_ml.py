from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ml', 'account.return.type')
    def _get_ml_account_return_type(self):
        return {
            'l10n_ml_reports.ml_tax_return_type': {
                'tax_payable_account_id': 'pcg_4441',
                'tax_receivable_account_id': 'pcg_4445',
            },
        }

    @template('ml_syscebnl', 'account.return.type')
    def _get_ml_syscebnl_account_return_type(self):
        return {
            'l10n_ml_reports.ml_tax_return_type': {
                'tax_payable_account_id': 'syscebnl_444',
                'tax_receivable_account_id': 'syscebnl_4441',
            },
        }
