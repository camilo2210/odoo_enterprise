# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from contextlib import contextmanager
from unittest.mock import patch

import requests

from odoo import Command
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tests import TransactionCase, tagged
from odoo.addons.delivery_envia.models.envia_request import STATE_CODE_MAP_ENVIA, Envia


@contextmanager
def _mock_envia_call(specific_envia_check=None):
    def _mock_request(*args, **kwargs):
        method = kwargs.get('method') or args[1]
        url = kwargs.get('url') or args[2]
        responses = {
            'GET': {
                'available-service': {
                    'data': [
                        {'carrier_id': 103, 'carrier_name': 'ups', 'id': 240, 'name': 'saver', 'description': 'UPS Express Saver', 'international': False},
                        {'carrier_id': 109, 'carrier_name': 'shippify', 'id': 255, 'name': 'express', 'description': 'Shippify Express', 'international': False},
                        {'carrier_id': 109, 'carrier_name': 'shippify', 'id': 256, 'name': 'slots', 'description': 'Shippify Slots', 'international': True},
                        {'carrier_id': 113, 'carrier_name': 'Jadlog', 'id': 265, 'name': 'expresso', 'description': 'Expresso', 'international': False},
                    ]
                },
                'additional-services': {
                    'data': [
                        {"name": "insurance", "description": "Insurance", "childs": [{"id": 14, "name": "insurance", "description": "Description", "json_structure": ""}]},
                        {"name": "liftgate_delivery", "description": "Liftgate Delivery", "childs": [{"id": 60, "name": "liftgate_delivery", "description": "Description", "json_structure": ""}]},
                        {"name": "lifgate_pickup", "description": "Lifgate Pickup", "childs": [{"id": 63, "name": "liftgate_pickup", "description": "Description", "json_structure": ""}]},
                        {"name": "pickup_residential", "description": "Pickup Residential", "childs": [{"id": 62, "name": "pickup_residential_zone", "description": "Pickup Residential Zone", "json_structure": ""}]},
                        {"name": "delivery_residential", "description": "Delivery Residential", "childs": [{"id": 61, "name": "delivery_residential_zone", "description": "Delivery Residential Zone", "json_structure": ""}]}
                    ]
                },
                'generic-form': [
                        {'fieldId': 'address1', 'fieldName': 'street', 'rules': {'required': True, 'validationType': 'street'}},
                        {'fieldId': 'address2', 'fieldName': 'number', 'rules': {'required': False, 'validationType': 'value'}},
                        {'fieldId': 'postalCode', 'fieldName': 'postal_code', 'rules': {'required': True, 'max': '20', 'validationType': 'value'}},
                        {'fieldId': 'city', 'fieldName': 'city', 'rules': {'required': True, 'max': '50', 'validationType': 'value'}},
                        {'fieldId': 'city_select', 'fieldName': 'city_select', 'rules': {'required': False, 'max': '50'}},
                        {'fieldId': 'state', 'fieldName': 'state', 'rules': {'required': True, 'min': '2', 'max': '3', 'validationType': 'select'}},
                        {'fieldId': 'reference', 'fieldName': 'reference', 'rules': {'required': False, 'max': '50'}}
                    ],
                'zipcode/CO/730001': [{
                    'zip_code': '730001',
                    'country': {'name': 'Colombia', 'code': 'CO'},
                    'state': {'name': 'Tolima', 'code': {'1digit': None, '2digit': 'TO', '3digit': 'TOL'}},
                    'locality': 'San Antonio',
                    'suburbs': ['73675000'],
                    'info': {'stat': '73001', 'stat_8digit': '73001000'},
                    'regions': {'region_1': 'Tolima', 'region_2': 'Ibagué', 'region_3': 'Ibagué'},
                }],
                'uploads/ups': ['WyJtb2NrTGFiZWw9PT09Il0=']
            },
            'POST': {
                'ship/rate': {
                    'meta': 'rate',
                    'data': [
                        {'carrier': 'ups', 'carrierDescription': 'UPS', 'carrierId': 103, 'serviceId': 240, 'quantity': 1, 'basePrice': 4.60, 'totalPrice': 4.60}
                    ]
                },
                'ship/generate': {
                    'meta': 'generate',
                    'data': [
                        {
                            'carrier': 'ups',
                            'service': 'saver',
                            'shipmentId': 1890000,
                            'trackingNumber': '1Z48746Q48746',
                            'trackUrl': 'https://test.envia.com/rastreo?label=1Z48746Q48746&cntry_code=us',
                            'label': 'https://s3.us-east-2.amazonaws.com/envia-staging/uploads/ups/1Z48746Q487462219663ea5a6a7da1.png',
                            'additionalFiles': [],
                            'totalPrice': 5.20,
                            'currency': 'USD'
                        }
                    ]
                },
            }
        }

        for endpoint, content in responses[method].items():
            if endpoint in url:
                if specific_envia_check:
                    specific_envia_check(endpoint, json.loads(kwargs.get('data') or '{}'))
                response = requests.Response()
                response._content = json.dumps(content).encode()
                response.status_code = 200
                return response

        raise Exception('unhandled request url %s' % url)

    with patch.object(requests.Session, 'request', _mock_request):
        yield


@tagged('post_install', '-at_install')
class TestDeliveryEnvia(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.your_company = cls.env.ref("base.main_partner")
        cls.your_company.write({
            'name': 'Odoo MX',
            'country_id': cls.env.ref('base.mx').id,
            'street': 'Avenida Paseo de la Reforma 505',
            'street2': 'Cuauhtémoc',
            'state_id': cls.env.ref('base.state_mx_df').id,
            'city': 'Ciudad de México',
            'zip': '06500',
            'phone': '+52 55 1234 5678',
        })
        cls.br_partner = cls.env['res.partner'].create({
            'name': 'Odoo BR Partner',
            'country_id': cls.env.ref('base.br').id,
            'street': 'Av. Presidente Vargas 592',
            'street2': 'Curitaba',
            'state_id': cls.env.ref('base.state_br_rj').id,
            'city': 'Rio de Janeiro',
            'zip': '30071-001',
            'phone': '+55 11 96123-4567',
        })
        # partner in us (azure)
        cls.us_partner = cls.env['res.partner'].create({
            'name': 'Azure Interior',
            'street': '4557 De Silva St',
            'city': 'Fremont',
            'country_id': cls.env.ref('base.us').id,
            'zip': '94538',
            'state_id': cls.env.ref('base.state_us_5').id,
            'email': 'azure.Interior24@example.com',
            'phone': '(870)-931-0505',
        })
        cls.co_partner = cls.env['res.partner'].create({
            'name': 'Colombia Partner',
            'street': 'Crr 14 no. 149 - 75 int 10 Apto 402',
            'street2': 'Conjunto Monterrey, el salado',
            'city': 'Ibagué',
            'zip': '730001',
            'country_id': cls.env.ref('base.co').id,
            'state_id': cls.env.ref('base.state_co_14').id,
            'email': 'colombia@example.com',
            'phone': '+57 310 3460237',
        })
        cls.cl_partner = cls.env['res.partner'].create({
            'name': 'Chile Partner',
            'street': 'Avenida Providencia 1432, Depto 402',
            'street2': '',
            'city': 'Santiago',
            'zip': '8320000',
            'country_id': cls.env.ref('base.cl').id,
            'state_id': cls.env.ref('base.state_cl_13').id,
            'email': 'chile@example.com',
            'phone': '+56 9 4012 3456',
        })

        cls.product_to_ship1 = cls.env["product.product"].create({
            'name': 'Door with Legs',
            'type': 'consu',
            'weight': 10.0
        })

        cls.product_to_ship2 = cls.env["product.product"].create({
            'name': 'Door with Arms',
            'type': 'consu',
            'weight': 15.0
        })

        cls.envia = cls.env.ref('delivery_envia.delivery_carrier_envia')

        cls.envia.write({
            'envia_production_api_key': 'mock_key',
            'envia_sandbox_api_key': 'mock_key',
            'envia_service_code': 'saver',
            'envia_carrier_code': 'ups'
        })

    def test_rate_order(self):
        """ Set up a sale order for an BR client and ensure that the rate is computed properly. """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.br_partner.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_to_ship1.id
                }),
                Command.create({
                    'product_id': self.product_to_ship2.id
                })
            ]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.envia.id,
            'order_id': sale_order.id
        })

        with _mock_envia_call():
            choose_delivery_carrier.update_price()
            self.assertEqual(choose_delivery_carrier.delivery_price, 4.60)

    def test_rate_order_without_address(self):
        """ Set up a sale order without address and ensure that the rate computation fails. """
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'phone': '(870)-931-0505',
        })

        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_to_ship1.id
                })
            ]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.envia.id,
            'order_id': sale_order.id
        })

        with _mock_envia_call():
            with self.assertRaises(UserError):
                choose_delivery_carrier.update_price()

    def test_envia_code_map_data_integrity(self):
        """
        Check the integrity of data used in the STATE_CODE_MAP_ENVIA used to convert
        Odoo's nomenclature to envia's one.
        """
        country_codes, state_codes = map(set, zip(*STATE_CODE_MAP_ENVIA))
        state_domain = Domain([('code', 'in', state_codes), ('country_id.code', 'in', country_codes)])
        state_match = self.env['res.country.state'].search(state_domain).grouped('code')

        def is_valid(country_code, state_code):
            return any(state.country_id.code == country_code for state in state_match[state_code])

        self.assertTrue(
            all(is_valid(country_code, state_code) for country_code, state_code in STATE_CODE_MAP_ENVIA),
            'Each country/state code combination must be represented by an existing state in Odoo'
        )

    def test_prepare_address_values_uses_envia_codes(self):
        envia_request = Envia(self.envia, prod_environment=True, debug_logger=lambda *args, **kwargs: None)

        # Colombia
        with _mock_envia_call():
            address = envia_request._prepare_address_values(self.co_partner, is_cust=True)

        self.assertEqual(address['city'], '73001000')
        self.assertEqual(address['city_select'], 'Ibagué')
        self.assertEqual(address['postalCode'], '73001000')
        self.assertEqual(address['state'], self.co_partner.state_id.code)

        # Chile
        with _mock_envia_call():
            address = envia_request._prepare_address_values(self.cl_partner, is_cust=True)

        self.assertEqual(address['city'], 'Santiago')
        self.assertEqual(address['postalCode'], '8320000')
        # Check that the envia state code is used
        country_code, state_code = self.cl_partner.country_id.code, self.cl_partner.state_id.code
        self.assertEqual(address['state'], STATE_CODE_MAP_ENVIA.get((country_code, state_code)))

    def test_shipping_order(self):
        """ Ensure that the shipping of an order works properly. """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.br_partner.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_to_ship1.id
                }),
                Command.create({
                    'product_id': self.product_to_ship2.id
                })
            ]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.envia.id,
            'order_id': sale_order.id
        })
        with _mock_envia_call():
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order.action_confirm()
            self.assertGreater(len(sale_order.picking_ids), 0, "The Sales Order did not generate pickings for shipment.")

            picking = sale_order.picking_ids[0]
            self.assertEqual(picking.carrier_id.id, sale_order.carrier_id.id, "The carrier is not the same on Picking and on SO.")
            picking.action_assign()
            picking.move_ids.picked = True
            self.assertGreater(picking.weight, 0.0, "The picking weight should be positive.")

            picking._action_done()
            self.assertEqual(picking.carrier_tracking_ref, "1Z48746Q48746", "The Envia Parcel Reference is not correct.")

            # Check that we the PDF is there with the correct title.
            pdf = picking.message_ids.attachment_ids.filtered(lambda m: m.description == 'LabelShipping-envia-1Z48746Q48746.PDF')
            self.assertNotEqual(pdf, self.env['ir.attachment'], "The label should be present as a pdf attachment.")

    def test_shipping_with_insurance(self):
        """
        Ensure insurance information is included when getting a rate and booking the shipment.
        """
        def insurance_format_check(endpoint, payload):
            if endpoint in ['ship/rate', 'ship/generate']:
                insurance_service = [
                    s for s in payload['packages'][0]['additionalServices']
                    if s['service'] == 'envia_insurance' and s.get('data', {}).get('amount', '0') == '40.0'
                ]
                self.assertTrue(insurance_service)

        self.envia.shipping_insurance = 50
        sale_order = self.env['sale.order'].create({
            'partner_id': self.br_partner.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_to_ship1.id,
                    'price_unit': 42,
                }),
                Command.create({
                    'product_id': self.product_to_ship2.id,
                    'price_unit': 38,
                })
            ]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.envia.id,
            'order_id': sale_order.id
        })
        with _mock_envia_call(insurance_format_check):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order.action_confirm()
            self.assertGreater(len(sale_order.picking_ids), 0)

            picking = sale_order.picking_ids[0]
            picking.action_assign()
            picking.move_ids.picked = True
            self.assertGreater(picking.weight, 0.0)

            picking._action_done()


@tagged('post_install', '-at_install')
class TestDeliveryEnviaWithLocalisations(TestDeliveryEnvia):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        required_locas = [
            'l10n_co_edi',
        ]

        if not all(loca.state == 'installed' for loca in cls.env['ir.module.module'].search([('name', 'in', required_locas)])):
            cls.skipTest(cls, "This class requires for localisations to be installed")

        cls.co_partner_2 = cls.env['res.partner'].create({
            'name': 'Colombia Partner in Medellin',
            'street': 'Cra. 25a #1 A Sur 45 local 1009',
            'street2': '',
            'city': '',
            'zip': '050011',
            'city_id': cls.env.ref('l10n_co_edi.city_co_01').id,
            'country_id': cls.env.ref('base.co').id,
            'state_id': cls.env.ref('base.state_co_01').id,
            'email': 'colombia@example.com',
            'phone': '+57 310 3460239',
        })

    def test_prepare_address_values(self):
        envia_request = Envia(self.envia, prod_environment=True, debug_logger=lambda *args, **kwargs: None)

        with _mock_envia_call():
            address = envia_request._prepare_address_values(self.co_partner_2, is_cust=True)

        self.assertEqual(address['city'], '05001000')
        self.assertEqual(address['city_select'], 'MEDELLÍN')
        self.assertEqual(address['postalCode'], '05001000')
        self.assertEqual(address['state'], self.co_partner_2.state_id.code)
