# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import fields, models, api
from datetime import datetime, timedelta


class UrbanPiperTestOrderWizard(models.TransientModel):
    _name = 'pos.urbanpiper.test.order.wizard'
    _description = 'Urbanpiper test order wizard'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        help='Test order product',
        domain="[('available_in_pos', '=', True)]"
    )
    quantity = fields.Integer(
        string='Quantity',
        default=1,
        help='Test order quantity',
    )
    discount_amount = fields.Float(
        string="Order Level Discount",
        default=0.0,
        help="Fixed discount applied on the entire order."
    )
    packaging_charge = fields.Integer(
        string='Packaging Charge',
        help='Packaging charge for test order.'
    )
    delivery_charge = fields.Integer(
        string='Delivery Charge',
        help='Delivery charges for test order.'
    )
    delivery_instruction = fields.Char(
        string='Delivery Instructions',
        help='Instructions for test order.'
    )
    delivery_provider_id = fields.Many2one(
        'pos.delivery.provider',
        string='Delivery Provider',
        help='Responsible delivery provider for test order, e.g., UberEats, Zomato.'
    )
    available_ptav_ids = fields.Many2many(
        'product.template.attribute.value',
        string='Available Product Options',
        compute='_compute_available_ptav_ids'
    )
    ptav_ids = fields.Many2many(
        'product.template.attribute.value',
        'pos_urbanpiper_test_order_wizard_ptav_rel',
        string='Product Options',
        help='Product options for test order.',
        domain="[('id', 'in', available_ptav_ids)]"
    )
    is_instant_order = fields.Boolean(string="Quick Order")
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help='Test order customer',
    )
    line_discount = fields.Float(
        string="Product Level Discount",
        default=0.0,
        help="Percentage discount applied on the product line."
    )

    @api.depends('product_id')
    def _compute_available_ptav_ids(self):
        for record in self:
            ptav_ids = False
            if record.product_id:
                ptav_ids = record.product_id.attribute_line_ids.product_template_value_ids.filtered(
                    lambda ptav: ptav.ptav_active
                )
            record.available_ptav_ids = ptav_ids

    def _get_customer_data(self, customer):
        customer_data = {
            'username': 'meet_jivani',
            'name': 'Meet Jivani',
            'id': 1111111,
            'phone': '+919999999999',
            'email': 'test_user@email.com',
            'address': {
                'is_guest_mode': False,
                'city': 'Gujarat',
                'pin': '380007',
                'line_1': '401 & 402, Floor 4, IT Tower 3',
                'line_2': 'InfoCity Gate, 1, Gandhinagar,',
                'sub_locality': 'Test Area',
            }
        }
        if not customer:
            return customer_data
        return {
            **customer_data,
            'name': customer.name,
            'phone': customer.phone,
            'email': customer.email,
            'address': {
                **customer_data['address'],
                'city': customer.city,
                'pin': customer.zip,
                'line_1': customer.street,
                'line_2': customer.street2,
            },
        }

    def test_order_json(self, data):
        product = data['product_id']
        tax_types = product.taxes_id.flatten_taxes_hierarchy().mapped('price_include')
        taxes = product.taxes_id.compute_all(
            product.list_price, product.currency_id, data['quantity']
        )
        unit_prices = product.taxes_id.compute_all(
            product.list_price, product.currency_id, 1
        )
        unit_price = unit_prices['total_included'] if tax_types and tax_types[0] else unit_prices['total_excluded']
        price_with_tax = taxes['total_included']
        price_without_tax = taxes['total_excluded']
        data['is_instant_order'] = self.is_instant_order
        payload = {
            'customer': self._get_customer_data(data['customer']),
            "order": {
                "next_states": ["Acknowledged", "Food Ready", "Dispatched", "Completed", "Cancelled"],
                "items": [{
                    "food_type": data['product_id'].urbanpiper_meal_type,
                    "total": price_without_tax,
                    "id": 1111111,
                    "title": data['product_id'].name,
                    "total_with_tax": price_with_tax,
                    "discounts": [],
                    "tags": [],
                    "price": unit_price,
                    "discount": 0.0,
                    "merchant_id": str(data['product_id'].id),
                    "instructions": "",
                    "charges": [],
                    "extras": {},
                    "image_url": None,
                    "total_charge": 0.0,
                    "is_recommended": False,
                    "quantity": data['quantity'],
                    "options_to_add": data['options_to_add'],
                    "taxes": [
                        {
                            "liability_on": "aggregator",
                            "rate": tax.amount,
                            "title": tax.tax_group_id.name,
                        }
                        for tax in data['product_id'].taxes_id
                    ],
                }],
                "details": {
                    "coupon": "",
                    "total_taxes": price_with_tax - price_without_tax,
                    "merchant_ref_id": None,
                    "order_level_total_charges": 0,
                    "id": data['delivery_identifier'],
                    "payable_amount": price_with_tax,
                    "total_external_discount": 0.0,
                    "order_total": price_with_tax,
                    "expected_pickup_time": int((datetime.now() + timedelta(minutes=25)).timestamp() * 1000),
                    "state": "Placed",
                    "discount": 0.0,
                    "channel": data['delivery_provider_id'].technical_name,
                    "delivery_datetime": int((datetime.now() + timedelta(minutes=data['delivery_datetime'])).timestamp() * 1000),
                    "item_level_total_charges": 0,
                    "item_taxes": 0.0,
                    "modified_to": None,
                    "item_level_total_taxes": price_with_tax - price_without_tax,
                    "order_state": "Placed",
                    "instructions": "Test order instructions",
                    "created": int(datetime.now().timestamp() * 1000),
                    "charges": [],
                    "country": "India",
                    "biz_name": "Odoo_IN",
                    "taxes": [],
                    "prep_time": {
                        "max": 85.0,
                        "adjustable": True,
                        "estimated": 25.0,
                        "min": 0.0
                    },
                    "ext_platforms": [{
                        "kind": "food_aggregator",
                        "name": data['delivery_provider_id'].technical_name,
                        "delivery_type": "Partner",
                        "extras": {
                            "order_otp": "4175",
                            "deliver_asap": True,
                            "is_delivery_charge_discounted": False,
                            "can_reject_order": True,
                            "is_instant_order": data.get("is_instant_order"),
                        },
                        "platform_store_id": "6546563516",
                        "id": "MNHLAW3L"
                    }],
                    "order_level_total_taxes": 0,
                    "order_subtotal": price_without_tax * data['quantity'],
                },
                "payment": [{
                    "amount": price_with_tax,
                    "option": "payment_gateway",
                    "srvr_trx_id": None
                }],
                "store": {
                    "city": "Gandhinagar",
                    "name": "Odoo India",
                    "merchant_ref_id": data['store'].store_identifier,
                    "address": "401 & 402, Floor 4, IT Tower 3 InfoCity Gate, 1, Gandhinagar, Gujarat 382007",
                    "id": 11111
                },
                "next_state": "Acknowledged",
                "urban_piper_test": True,
            }
        }
        charges = []
        if data['packaging_charge'] > 0:
            charges.append({
                'taxes': [
                    {
                        'rate': None,
                        'liability_on': 'aggregator',
                        'value': (data['packaging_charge'] * 15) / 100,
                        'title': 'VAT'
                    }
                ] if data['has_tax'] else [],
                'value': data['packaging_charge'],
                'title': 'Packaging Charge'
            })
        if data['delivery_charge'] > 0:
            charges.append({
                'taxes': [
                    {
                        'rate': None,
                        'liability_on': 'aggregator',
                        'value': (data['delivery_charge'] * 15) / 100,
                        'title': 'VAT'
                    }
                ] if data['has_tax'] else [],
                'value': data['delivery_charge'],
                'title': 'Delivery Charge'
            })
        payload["order"]["details"]["charges"] = charges
        discounts = []
        if data['discount_amount'] > 0:
            discounts.append({
                'is_merchant_discount': True,
                'code': 'CRICKET',
                'value': data['discount_amount'],
                'title': 'Merchant Discount'
            })
        payload['order']['details']['ext_platforms'][0]['discounts'] = discounts
        if data['delivery_instruction']:
            payload['order']['details']['instructions'] = data['delivery_instruction']
        line_discounts = []
        if data['line_discount'] > 0:
            line_discount_value = (taxes['total_included'] / data['quantity']) * data['line_discount'] / 100
            line_discounts.append({
                'is_merchant_discount': True,
                'code': 'TEST',
                'value': line_discount_value,
                'title': 'Merchant Discount',
            })
        payload['order']['items'][0]['discounts'] = line_discounts
        return payload

    def make_test_order(self, delivery_identifier=False):
        store = self.env['pos.urbanpiper.store'].browse(self.env.context.get('store_id'))
        options_to_add = [{
            'title': ptav.product_attribute_value_id.name,
            'quantity': '1',
            'merchant_id': f'{self.product_id.id}-{ptav.product_attribute_value_id.id}',
            'total_price': ptav.price_extra,
        } for ptav in self.ptav_ids]
        data = {
            'store': store,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'discount_amount': self.discount_amount,
            'line_discount': self.line_discount,
            'packaging_charge': self.packaging_charge,
            'delivery_charge': self.delivery_charge,
            'delivery_instruction': self.delivery_instruction,
            'delivery_provider_id': self.delivery_provider_id,
            'delivery_identifier': delivery_identifier or str(uuid.uuid4()),
            'options_to_add': options_to_add,
            'customer': self.partner_id,
            'has_tax': self.env.context.get('has_tax', True),
            'delivery_datetime': self.env.context.get('delivery_datetime', 25)
        }
        order_json = self.test_order_json(data)
        return self.env['pos.order'].process_urbanpiper_order_placed(order_json, store)
