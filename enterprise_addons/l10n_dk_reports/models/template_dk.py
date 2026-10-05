from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('dk', 'account.return.type')
    def _get_dk_account_return_type(self):
        return {
            'l10n_dk_reports.dk_tax_return_type': {
                'tax_payable_account_id': 'dk_coa_7840',
                'tax_receivable_account_id': 'dk_coa_6320',
            },
        }
