from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cl', model='product.product')
    def _get_product_cl_edi(self):
        return {
            'l10n_cl_edi.product_product_non_billable_amounts': {
                'property_account_expense_id': 'account_11320',
            },
        }
