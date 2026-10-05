from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _get_avatax_fp_tax_accounts(self, country_code):
        FiscalPosition = self.env['account.fiscal.position']
        invoice_accounts = FiscalPosition._default_avatax_invoice_account_id()
        refund_accounts = FiscalPosition._default_avatax_refund_account_id()
        tax_account_invoice_id = invoice_accounts.id if invoice_accounts else None
        tax_account_refund_id = refund_accounts.id if refund_accounts else None

        fallback_invoice = fallback_refund = False
        if country_code == 'us':
            fallback_invoice = fallback_refund = 'account_account_us_tax_received'
        elif country_code == 'ca':
            hst_states = ('ON', 'NB', 'NL', 'NS', 'PE')
            if self.env.company.state_id.code in hst_states:
                fallback_invoice = fallback_refund = 'l10n_ca_hst_received'
            else:
                fallback_invoice = fallback_refund = 'l10n_ca_gst_received'
        return {
            'avatax_invoice_account_id': tax_account_invoice_id or fallback_invoice,
            'avatax_refund_account_id': tax_account_refund_id or fallback_refund,
        }

    def _get_avatax_fiscal_position(self, country_code):
        return {
            f'account_fiscal_position_avatax_{country_code}': {
                'name': 'Automatic Tax Mapping (AvaTax)',
                'is_avatax': True,
                **self._get_avatax_fp_tax_accounts(country_code),
                'auto_apply': False,
                'country_id': self.env.ref(f'base.{country_code}').id,
                'sequence': 100,
            },
        }

    @template('us', 'account.fiscal.position')
    def _get_us_avatax_fiscal_position(self):
        return self._get_avatax_fiscal_position('us')

    @template('ca_2023', 'account.fiscal.position')
    def _get_ca_avatax_fiscal_position(self):
        return self._get_avatax_fiscal_position('ca')
