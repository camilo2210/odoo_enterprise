from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('tg', 'account.return.type')
    def _get_tg_account_return_type(self):
        return {
            'l10n_tg_reports.tg_tax_return_type': {
                'tax_payable_account_id': 'pcg_4441',
                'tax_receivable_account_id': 'pcg_4445',
            },
        }

    @template('tg_syscebnl', 'account.return.type')
    def _get_tg_syscebnl_account_return_type(self):
        return {
            'l10n_tg_reports.tg_tax_return_type': {
                'tax_payable_account_id': 'syscebnl_444',
                'tax_receivable_account_id': 'syscebnl_4441',
            },
        }
