# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        self._set_pos_urban_receipt_common_data(data)
        return data

    def _generate_preparation_receipt_data(self, order_change, is_split_per_product=False):
        data = super()._generate_preparation_receipt_data(order_change, is_split_per_product)
        for receipt in data:
            self._set_pos_urban_receipt_common_data(receipt)
        return data

    def _set_pos_urban_receipt_common_data(self, data):
        data['conditions']['is_urban_piper_order'] = bool(self.delivery_identifier)
        data['extra_data']['delivery_provider_name'] = self.delivery_provider_id.name if self.delivery_provider_id else False

        if self.delivery_identifier:
            data['extra_data']['delivery_provider_name'] = self.delivery_provider_id.name if self.delivery_provider_id else False

            if self.delivery_json:
                value = json.loads(self.delivery_json)
                customer_data = value.get('customer', {})
                address_data = customer_data.get('address', {})
                data['partner'] = {
                    **data.get('partner', {}),
                    'name': customer_data.get('name'),
                    'address': ', '.join(filter(None, [
                        address_data.get('line_1'),
                        address_data.get('line_2'),
                        address_data.get('city'),
                        address_data.get('pin'),
                    ])),
                    'phone': customer_data.get('phone'),
                    'email': customer_data.get('email'),
                }

                platform = value.get('order', {}).get('details', {}).get('ext_platforms', [])
                platform = platform[0] if platform else {}
                identifier = platform.get('id', "") or ""
                data['extra_data']['ext_platforms_id'] = [identifier[:-4], identifier[-4:]]
                data['extra_data']['delivery_otp'] = platform.get('extras', {}).get('order_otp', '')
                data['extra_data']['is_instant_order'] = platform.get('extras', {}).get('is_instant_order', False)
