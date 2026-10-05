from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('fr', 'account.return.type')
    def _get_fr_account_return_type(self):
        return {
            'l10n_fr_reports.vat_return_type': {
                'tax_payable_account_id': 'pcg_44551',
                'tax_receivable_account_id': 'pcg_44567',
            },
        }
