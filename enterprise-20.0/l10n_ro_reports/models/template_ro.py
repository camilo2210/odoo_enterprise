from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ro', 'account.return.type')
    def _get_ro_account_return_type(self):
        return {
            'l10n_ro_reports.ro_tax_return_type': {
                'tax_payable_account_id': 'pcg_44231',
                'tax_receivable_account_id': 'pcg_4424',
            },
        }
