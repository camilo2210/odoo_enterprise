from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ne', 'account.return.type')
    def _get_ne_account_return_type(self):
        return {
            'l10n_ne_reports.ne_tax_return_type': {
                'tax_payable_account_id': 'pcg_4441',
                'tax_receivable_account_id': 'pcg_4445',
            },
        }

    @template('ne_syscebnl', 'account.return.type')
    def _get_ne_syscebnl_account_return_type(self):
        return {
            'l10n_ne_reports.ne_tax_return_type': {
                'tax_payable_account_id': 'syscebnl_444',
                'tax_receivable_account_id': 'syscebnl_4441',
            },
        }
