import json
from contextlib import contextmanager
from unittest.mock import patch
import requests

from odoo.tests.common import tagged
from odoo import Command
from odoo.addons.delivery_ups_rest.tests.common import DeliveryUPSCommon
from odoo.tools import mute_logger
from odoo.tools.float_utils import float_repr
from odoo.exceptions import UserError


@contextmanager
def _mock_request_call(specific_ups_check=None):
    def _mock_request(*args, **kwargs):
        url = kwargs.get('url')
        if 'shipments' in url:
            url = url.split('/shipments')[1]
        responses = {
            'token': {'access_token': 'mock_token'},
            'rating': {'RateResponse': {
                'Response': {
                    "Alert": {"Code": "string", "Description": "string"},
                },
                'RatedShipment': {'TotalCharges': {'MonetaryValue': '5.5', 'CurrencyCode': 'USD'}}}},
            'ship': {'ShipmentResponse': {'ShipmentResults': {
                'ShipmentCharges': {'TotalCharges': {'MonetaryValue': '5.5', 'CurrencyCode': 'USD'}},
                'ShipmentIdentificationNumber': '123',
                'PackageResults': {'TrackingNumber': '123', 'ShippingLabel': {'GraphicImage': 'some_imag'}}
                }}},
            'cancel': {'VoidShipmentResponse': {'SummaryResult': {'Status': {}}}},
        }

        for endpoint, content in responses.items():
            if endpoint in url:
                if specific_ups_check:
                    specific_ups_check(endpoint, kwargs['json'])
                response = requests.Response()
                response._content = json.dumps(content).encode()
                response.status_code = 200
                return response

        raise Exception('unhandled request url %s' % url)

    with patch.object(requests.Session, 'request', _mock_request):
        yield


@tagged('post_install', '-at_install')
class TestDeliveryUPS(DeliveryUPSCommon):

    _test_user_groups = None  # FIXME list needed groups

    def setUp(self):
        super().setUp()

        self.env.company.partner_id.write({
            'country_id': self.env.ref('base.us').id,
            'state_id': self.env.ref('base.state_us_5').id,
            'city': 'Los Angelos',
            'street': 'My street',
            'phone': '1234567890',
            'zip': '1234',
        })

        self.product = self.env['product.product'].create({
            'name': 'fancy box',
            'type': 'consu',
            'weight': 10.0,
        })

        self.partner = self.env['res.partner'].create({
            'name': 'Cool Customer',
            'country_id': self.env.ref('base.us').id,
            'state_id': self.env.ref('base.state_us_5').id,
            'street': 'My street',
            'city': 'Los Angelos',
            'phone': '1234567890',
            'zip': '1234',
        })

        self.hong_kong_partner = self.env['res.partner'].create({
            'name': 'Hong Kong Customer',
            'country_id': self.env.ref('base.hk').id,
            'state_id': self.env.ref('base.state_hk_hk').id,
            'street': "1 H-K Road",
            'city': "Hong Kong",
            'phone': '1234567890',
            'zip': '999077',
        })

        self.philippino_partner = self.env['res.partner'].create({
            'name': 'PH Customer',
            'country_id': self.env.ref('base.ph').id,
            'state_id': self.env.ref('base.state_ph_26').id,
            'street': "1 Manille Road",
            'city': "Manille",
            'phone': '1234567890',
            'zip': '4607',
        })

    def test_ups_basic_flow(self):
        def delivery_confirmation_data_check(endpoint, payload):
            if endpoint == 'rating':
                shipment = payload['RateRequest']['Shipment']
                self.assertFalse(shipment['ShipmentServiceOptions'])
                self.assertEqual(shipment['PackageServiceOptions']['DeliveryConfirmation']['DCISType'], '2')

        self.ups_delivery.ups_require_signature = True
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': "Fancy box",
                'product_uom_qty': 1.0,
                'price_unit': 20,
            })]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.ups_delivery.id,
            'order_id': sale_order.id
        })
        with _mock_request_call(delivery_confirmation_data_check):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            self.assertEqual(choose_delivery_carrier.display_price, 5.5)
            sale_order.action_confirm()
            self.assertGreater(len(sale_order.picking_ids), 0, "The Sales Order did not generate pickings for shipment.")

            picking = sale_order.picking_ids[0]
            self.assertEqual(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")
            picking.action_assign()
            picking.move_line_ids[0].quantity = 1.0
            self.assertGreater(picking.weight, 0.0, "Picking weight should be positive.")
            picking._action_done()
            self.assertEqual(picking.carrier_tracking_ref, '123', 'Tracking ref should be set from mock response')
            self.assertEqual(picking.carrier_price, 5.5, 'Price should be set from mock response')
            picking.cancel_shipment()
            self.assertEqual(picking.carrier_tracking_ref, False, 'Shipment cancel failed')

    def test_ups_rest_sends_correct_delivery_type_for_amazon(self):
        amazon_expected_delivery_type = self.ups_delivery._get_delivery_type()
        self.assertEqual(amazon_expected_delivery_type, 'ups')

    def test_ups_invoice_uses_correct_currency(self):
        usd = self.env.ref('base.USD')
        eur = self.env.ref('base.EUR')
        pricelists = self.env['product.pricelist'].create([
            {
                'name': 'USD Pricelist',
                'currency_id': usd.id,
            },
            {
                'name': 'EUR Pricelist',
                'currency_id': eur.id,
            },
        ])
        for pricelist in pricelists:
            sale_order = self.env['sale.order'].create({
                'partner_id': self.partner.id,
                'pricelist_id': pricelist.id,
                'order_line': [Command.create({
                    'product_id': self.product.id,
                    'name': "Fancy box",
                    'product_uom_qty': 1.0,
                    'price_unit': 20,
                })]
            })
            wiz_action = sale_order.action_open_delivery_wizard()
            choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
                'carrier_id': self.ups_delivery.id,
                'order_id': sale_order.id
            })
            with _mock_request_call():
                choose_delivery_carrier.update_price()
                choose_delivery_carrier.button_confirm()
                sale_order.action_confirm()
                picking = sale_order.picking_ids[0]
                picking.action_assign()
                picking._action_done()
                _, shipment_info, _, _, _ = self.ups_delivery._prepare_shipping_data(picking)
                self.assertEqual(shipment_info['itl_currency_code'], pricelist.currency_id.name)

    def test_ups_commercial_invoice_freight_charge(self):
        '''
        Ensure freight charge is correctly transmitted for internatonal UPS deliveries.
        '''
        def freight_charge_check(endpoint, payload):
            if endpoint == 'ship':
                payload_freight_charge = payload['ShipmentRequest']['Shipment']['ShipmentServiceOptions']['InternationalForms']['FreightCharges']['MonetaryValue']
                self.assertEqual(payload_freight_charge, freight_charge)

        sale_order = self.env['sale.order'].create({
            'partner_id': self.hong_kong_partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': "Fancy box",
                'product_uom_qty': 1.0,
                'price_unit': 20,
            })]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.ups_delivery.id,
            'order_id': sale_order.id
        })
        with _mock_request_call(freight_charge_check):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order.action_confirm()
            freight_charge = float_repr(sale_order.order_line.filtered(lambda sol: sol.is_delivery).price_total, sale_order.currency_id.decimal_places)
            picking = sale_order.picking_ids[0]
            picking._action_done()

    def test_ups_partner_with_long_address_fields(self):
        '''
        Ensure the different fields of the client's address are sanitised before being sent to UPS.
        '''
        def client_address_format_check(endpoint, payload):
            if endpoint == 'ship':
                client_address = payload['ShipmentRequest']['Shipment']['ShipTo']['Address']
                # StateProvinceCode should be empty as the field is only used for countries US, CA, IE and VN
                self.assertEqual(client_address['StateProvinceCode'], '')
                # PostalCode should be only the first 9 alpha-num chars of the contact's zip
                self.assertEqual(client_address['PostalCode'], '123456789')

        self.philippino_partner.zip = "12 3.45-67/8901"
        sale_order = self.env['sale.order'].create({
            'partner_id': self.philippino_partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': "Fancy box",
                'product_uom_qty': 1.0,
                'price_unit': 20,
            })]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.ups_delivery.id,
            'order_id': sale_order.id
        })
        with _mock_request_call(client_address_format_check):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order.action_confirm()
            self.assertGreater(len(sale_order.picking_ids), 0)

            picking = sale_order.picking_ids[0]
            picking.action_assign()
            picking.move_line_ids[0].quantity = 1.0
            picking._action_done()

    @mute_logger('odoo.tools.translate')
    def test_ups_commercial_invoice_with_different_delivery_and_invoice_address(self):
        '''
        Ensure the commercial invoice uses the partner's delivery address and invoicing address when
        specified. If the 2 address' country are different, ensure 'SoldTo' defaults to the delivery
        address (because UPS does not accept for them to be in different countries).
        '''
        def same_country_commercial_invoice_address_check(endpoint, payload):
            if endpoint == 'ship':
                ship_to = payload['ShipmentRequest']['Shipment']['ShipTo']
                sold_to = payload['ShipmentRequest']['Shipment']['ShipmentServiceOptions']['InternationalForms']['Contacts']['SoldTo']
                self.assertEqual(ship_to['Address']['AddressLine'][0], delivery_address.street)
                self.assertEqual(sold_to['Address']['AddressLine'][0], invoicing_address.street)
                # Ensure sold_to name falls back to the parent if the invoicing address has no name
                self.assertEqual(sold_to['AttentionName'], self.hong_kong_partner.name)

        def different_country_commercial_invoice_address_check(endpoint, payload):
            if endpoint == 'ship':
                ship_to = payload['ShipmentRequest']['Shipment']['ShipTo']
                sold_to = payload['ShipmentRequest']['Shipment']['ShipmentServiceOptions']['InternationalForms']['Contacts']['SoldTo']
                self.assertEqual(ship_to['Address']['AddressLine'][0], sold_to['Address']['AddressLine'][0])
                self.assertEqual(sold_to['Address']['AddressLine'][0], delivery_address.street)

        delivery_address, invoicing_address = self.env['res.partner'].create([
            {
                'name': 'Hong Kong Delivery Address',
                'type': 'delivery',
                'country_id': self.env.ref('base.hk').id,
                'street': 'Delivery Street 1',
                'state_id': self.env.ref('base.state_hk_hk').id,
                'city': "Hong Kong",
                'phone': '1234567890',
                'zip': '999077',
                'parent_id': self.hong_kong_partner.id,
            },
            {
                'name': False,  # By default, invoicing addresses are created without a name
                'type': 'invoice',
                'country_id': self.env.ref('base.hk').id,
                'street': 'Invoicing Street 1',
                'state_id': self.env.ref('base.state_hk_hk').id,
                'city': "Hong Kong",
                'phone': '1234567890',
                'zip': '999077',
                'parent_id': self.hong_kong_partner.id,
            },
        ])

        sale_order_1, sale_order_2 = self.env['sale.order'].create([
            {
                'partner_id': self.hong_kong_partner.id,
                'order_line': [Command.create({
                    'product_id': self.product.id,
                    'name': "Fancy box",
                    'product_uom_qty': 1.0,
                    'price_unit': 20,
                })]
            },
            {
                'partner_id': self.hong_kong_partner.id,
                'order_line': [Command.create({
                    'product_id': self.product.id,
                    'name': "Fancy box",
                    'product_uom_qty': 3.0,
                    'price_unit': 30,
                })]
            },
        ])

        wiz_action = sale_order_1.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.ups_delivery.id,
            'order_id': sale_order_1.id
        })
        with _mock_request_call(same_country_commercial_invoice_address_check):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order_1.action_confirm()
            self.assertGreater(len(sale_order_1.picking_ids), 0)

            picking = sale_order_1.picking_ids[0]
            picking.action_assign()
            picking.move_line_ids[0].quantity = 1.0
            picking._action_done()

        delivery_address.country_id = self.env.ref('base.uk')
        wiz_action = sale_order_2.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.ups_delivery.id,
            'order_id': sale_order_2.id
        })
        with _mock_request_call(different_country_commercial_invoice_address_check):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            sale_order_2.action_confirm()
            self.assertGreater(len(sale_order_2.picking_ids), 0)

            picking = sale_order_2.picking_ids[0]
            picking.action_assign()
            picking.move_line_ids[0].quantity = 1.0
            picking._action_done()

    @mute_logger('odoo.tools.translate')
    def test_ups_phone_length(self):
        """
        Tests that the phone numbers for a delivery with ups sticks to the
        documentation, meaning having less than 15 characters should work,
        while having more should raise an error.
        """
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'name': "Fancy box",
                'product_uom_qty': 1.0,
                'price_unit': 20,
            })]
        })
        wiz_action = sale_order.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.ups_delivery.id,
            'order_id': sale_order.id
        })
        sale_order.warehouse_id.partner_id = self.hong_kong_partner

        self.partner.phone = '1234567891011121'
        with _mock_request_call():
            with self.assertRaises(UserError, msg="Recipient Phone should not exceed 15 characters") as ue_ship_to_long:
                choose_delivery_carrier.update_price()
            self.assertIn("Recipient Phone must be between 1 and 15", str(ue_ship_to_long.exception))
            self.partner.phone = ' '
            with self.assertRaises(UserError, msg="Recipient Phone should be at least 1 character") as ue_ship_to_short:
                choose_delivery_carrier.update_price()
            self.assertIn("Recipient Phone must be between 1 and 15", str(ue_ship_to_short.exception))

            self.partner.phone = '123456789'
            choose_delivery_carrier.update_price()

            sale_order.warehouse_id.partner_id.phone = '1234567891011121'
            with self.assertRaises(UserError, msg="Warehouse Phone should not exceed 15 characters") as ue_warehouse_long:
                choose_delivery_carrier.update_price()
            self.assertIn("Warehouse Phone must be between 1 and 15", str(ue_warehouse_long.exception))
            sale_order.warehouse_id.partner_id.phone = ' '
            with self.assertRaises(UserError, msg="Warehouse Phone should be at least 1 character") as ue_warehouse_short:
                choose_delivery_carrier.update_price()
            self.assertIn("Warehouse Phone must be between 1 and 15", str(ue_warehouse_short.exception))

            sale_order.warehouse_id.partner_id.phone = '123456789'
            self.env.company.partner_id.phone = '1234567891011121'
            with self.assertRaises(UserError, msg="Shipper Phone should not exceed 15 characters") as ue_shipper_long:
                choose_delivery_carrier.update_price()
            self.assertIn("Shipper Phone must be between 1 and 15", str(ue_shipper_long.exception))
            self.env.company.partner_id.phone = ' '
            with self.assertRaises(UserError, msg="Shipper Phone should be at least 1 character") as ue_shipper_short:
                choose_delivery_carrier.update_price()
            self.assertIn("Shipper Phone must be between 1 and 15", str(ue_shipper_short.exception))
