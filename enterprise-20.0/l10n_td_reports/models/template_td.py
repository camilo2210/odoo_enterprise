from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('td', 'account.return.type')
    def _get_td_account_return_type(self):
        return {
            'l10n_td_reports.td_tax_return_type': {
                'tax_payable_account_id': 'pcg_4441',
                'tax_receivable_account_id': 'pcg_4445',
            },
        }

    @template('td_syscebnl', 'account.return.type')
    def _get_td_syscebnl_account_return_type(self):
        return {
            'l10n_td_reports.td_tax_return_type': {
                'tax_payable_account_id': 'syscebnl_444',
                'tax_receivable_account_id': 'syscebnl_4441',
            },
        }
