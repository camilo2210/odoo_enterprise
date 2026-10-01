# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        if self.company_id.country_id.code != 'BR':
            return data

        ava = self.l10n_br_edi_avatax_data
        if ava:
            ava_headers = ava.get('header', {})
            locations = ava_headers.get("locations", {})
            establishment_full_address = ''
            entity_full_address = ''
            state_tax_id = ''
            qr_code_data = ''

            if locations.get('establishment'):
                establishment = locations['establishment']
                establishment_full_address = self.get_l10n_br_location_full_address(establishment.get('address'))
                state_tax_id = establishment.get('stateTaxId', '')

            if locations.get('entity'):
                entity_full_address = self.get_l10n_br_location_full_address(locations['entity'].get('address'))

            formatted_key = self.l10n_br_edi_access_key or ''
            formatted_key = ' '.join([formatted_key[i:i + 4] for i in range(0, len(formatted_key), 4)])

            if ava_headers.get('goods'):
                qr_code_data = self._order_receipt_generate_qr_code(ava_headers["goods"].get("nfceQrCode"))

            data['extra_data']['l10n_br_edi_avatax_data'] = {
                **self.l10n_br_edi_avatax_data,
                'establishment_full_address': establishment_full_address,
                'entity_full_address': entity_full_address,
                'state_tax_id': state_tax_id,
                'items_count': len(self.lines.product_id),
                'formatted_key': formatted_key,
                'qr_code_data': qr_code_data,
                'header': ava_headers,
            }

        if self.partner_id and (label := self.partner_id._get_preferred_legal_entity_identifier_vals().get('label')):
            # the CNPJ has no label of its own, the country one ('CNPJ') is then kept
            data['extra_data']['partner_vat_label'] = str(label)

        data['conditions']['l10n_br_avalara_environment_sandbox'] = bool(self.company_id.l10n_br_avalara_environment == 'sandbox')
        data['conditions']['l10n_br_is_nfce'] = bool(self.config_id.l10n_br_is_nfce)
        return data

    def get_l10n_br_location_full_address(self, address):
        if not address:
            return ""
        return ", ".join(
            str(v) for v in [
                address.get("street"),
                address.get("number"),
                address.get("neighborhood"),
                address.get("cityName"),
                address.get("state"),
            ]
            if v
        )
