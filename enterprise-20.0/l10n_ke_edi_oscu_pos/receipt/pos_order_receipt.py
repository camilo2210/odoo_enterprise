# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        data['conditions']['code_ke'] = self.company_id.country_id.code == 'KE'

        if not data['conditions']['code_ke'] or not self.l10n_ke_order_json:
            return data
        values = self.l10n_ke_order_json

        tax_types = {'B': '16%', 'E': '8%', 'C': '0%', 'D': 'Non-VAT', 'A': 'Exempt'}
        taxes = []
        for type, rate in tax_types.items():
            taxable_amount = values.get(f'taxblAmt{type}', 0.0) * (-1 if self.is_refund_or_negative() else 1)
            tax_amount = values.get(f'taxAmt{type}', 0.0) * (-1 if self.is_refund_or_negative() else 1)
            total_amount = taxable_amount + tax_amount
            taxes.append({
                'rate': rate,
                'taxable_amount': taxable_amount,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
            })

        taxes.append({
            'rate': 'Total',
            'taxable_amount': sum(t['taxable_amount'] for t in taxes),
            'tax_amount': sum(t['tax_amount'] for t in taxes),
            'total_amount': sum(t['total_amount'] for t in taxes),
        })

        for t in taxes:
            t['taxable_amount'] = values.get('totTaxblAmt', 0.0) * (-1 if self.is_refund_or_negative() else 1)
            t['tax_amount'] = values.get('totTaxAmt', 0.0) * (-1 if self.is_refund_or_negative() else 1)
            t['total_amount'] = values.get('totAmt', 0.0) * (-1 if self.is_refund_or_negative() else 1)

        data['image']['l10n_ke_edi_oscu_pos_qrsrc'] = self._order_receipt_generate_qr_code(self._get_l10n_ke_edi_oscu_pos_qrurl())
        data['extra_data']['l10n_ke_edi_oscu_taxes'] = taxes or False
        data['extra_data']['l10n_ke_oscu_serial_number'] = self.company_id.l10n_ke_oscu_serial_number

        return data
