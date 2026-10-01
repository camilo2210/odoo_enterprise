from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('sg', 'account.return.type')
    def _get_sg_account_return_type(self):
        return {
            'l10n_sg_reports.sg_tax_return_type': {
                'tax_payable_account_id': 'l10n_sg_430700',
                'tax_receivable_account_id': 'l10n_sg_220600',
                'advance_tax_payment_account_id': 'l10n_sg_230100',
            },
        }
