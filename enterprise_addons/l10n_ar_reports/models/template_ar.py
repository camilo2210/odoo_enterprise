from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template(model='account.return.type')
    def _get_ar_account_return_type(self, template_code):
        if template_code not in ('ar_base', 'ar_ex', 'ar_ri'):
            return {}

        if template_code == 'ar_ri':
            payable, receivable = 'ri_iva_saldo_a_pagar', 'ri_iva_saldo_tecnico_favor'
        else:
            payable, receivable = 'base_default_vat', 'base_default_vat_receivable'

        return {
            'l10n_ar_reports.ar_tax_return_type': {
                'tax_payable_account_id': payable,
                'tax_receivable_account_id': receivable,
            },
        }
