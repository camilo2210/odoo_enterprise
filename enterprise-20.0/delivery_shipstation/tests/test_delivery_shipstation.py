# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import MockHTTPClient

API_URL = 'https://api.shipstation.com'
RATES_URL = f'{API_URL}/v2/rates'
LABELS_URL = f'{API_URL}/v2/labels'

CARRIER_CODE = 'se-4770975'
LABEL_ID = 'se-124950590'
RETURN_LABEL_ID = 'se-124950591'
VOID_URL = f'{LABELS_URL}/{LABEL_ID}/void'
RETURN_URL = f'{LABELS_URL}/{LABEL_ID}/return'

TRACKING_NUMBER = '1Z130F9D0327027347'
RETURN_TRACKING_NUMBER = '1Z130F9D0327027348'

# Base64 of a tiny placeholder payload, as ShipStation inlines the label content.
PDF_LABEL_CONTENT = "WW91J3JlIGEgY3VyaW91cyBvbmUgYXJlbid0IHlvdQ=="
ZPL_LABEL_CONTENT = "XlhBXkZPNTAsNTBeQUROLDM2LDIwXkZET2Rvb15GU15YWg=="

RATES_RESPONSE = {
    'rate_response': {
        'rates': [{
            'rate_id': 'se-401300184',
            'rate_type': 'shipment',
            'carrier_id': CARRIER_CODE,
            'shipping_amount': {'currency': 'usd', 'amount': 11.92},
            'insurance_amount': {'currency': 'usd', 'amount': 0.99},
            'confirmation_amount': {'currency': 'usd', 'amount': 0.0},
            'other_amount': {'currency': 'usd', 'amount': 0.0},
            'warning_messages': [],
        }],
    },
}

NO_RATES_RESPONSE = {
    'rate_response': {
        'rates': [],
        'invalid_rates': [],
        'status': 'error',
        'errors': [{'message': "A shipping carrier error occurred: Missing or Invalid DestinationCountry"}],
    },
}


def _label_response(label_id, tracking_number, label_format='pdf'):
    """ Build a ShipStation label/return response for the given inline label format. """
    content = ZPL_LABEL_CONTENT if label_format == 'zpl' else PDF_LABEL_CONTENT
    download = {'href': f'data:application/{label_format};base64,{content}'}
    return {
        'label_id': label_id,
        'label_download': download,
        'tracking_number': tracking_number,
        'shipment_cost': {'currency': 'usd', 'amount': 11.92},
        'insurance_cost': {'currency': 'usd', 'amount': 0.99},
        'packages': [{
            'tracking_number': tracking_number,
            'label_download': download,
        }],
    }


@tagged('post_install', '-at_install')
class TestDeliveryShipStation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.your_company = cls.env.ref("base.main_partner")
        cls.your_company.write({
            'name': 'Odoo Inc.',
            'street': '8000 Marina Blvd, Suite 300',
            'city': 'Brisbane',
            'zip': '94005',
            'country_id': cls.env.ref('base.us').id,
            'state_id': cls.env.ref('base.state_us_5').id,
            'phone': '+1 555-555-5556',
            'website': 'www.example.com',
            'email': 'info@yourcompany.com',
        })
        cls.us_partner = cls.env['res.partner'].create({
            'name': 'Odoo Inc. Partner',
            'street': '250 Executive Park Blvd, Suite 3400',
            'city': 'San Fransisco',
            'zip': '94134',
            'country_id': cls.env.ref('base.us').id,
            'state_id': cls.env.ref('base.state_us_5').id,
            'phone': '+1 555-555-5556',
        })

        cls.product_to_ship1 = cls.env["product.product"].create({
            'name': 'Door with Legs',
            'type': 'consu',
            'weight': 10.0,
        })

        cls.product_to_ship2 = cls.env["product.product"].create({
            'name': 'Door with Arms',
            'type': 'consu',
            'weight': 15.0,
        })

        cls.shipstation = cls.env.ref('delivery_shipstation.delivery_carrier_shipstation')

        cls.shipstation.write({
            'shipstation_production_api_key': 'mock_key',
            'shipstation_service_code': 'ups_ground',
            'shipstation_carrier_code': CARRIER_CODE,
            'shipstation_supports_multipackage': True,
            'shipstation_supports_returns': False,
            'prod_environment': True,
        })

    # -------------------------------------------------------------------------
    # ENDPOINT MOCKS
    # -------------------------------------------------------------------------

    def _mock_rates(self, response=RATES_RESPONSE, status=200):
        """ Mock ``POST v2/rates``, the rate request endpoint. """
        return MockHTTPClient(url=RATES_URL, method='POST', return_json=response, return_status=status)

    def _mock_labels(self, label_format='pdf'):
        """ Mock ``POST v2/labels``, the label purchase endpoint. """
        return MockHTTPClient(
            url=LABELS_URL,
            method='POST',
            return_json=_label_response(LABEL_ID, TRACKING_NUMBER, label_format),
        )

    def _mock_void(self, response=None):
        """ Mock ``PUT v2/labels/<label_id>/void``, the label cancellation endpoint. """
        return MockHTTPClient(url=VOID_URL, method='PUT', return_json=response or {'approved': True})

    def _mock_return(self, label_format='pdf'):
        """ Mock ``POST v2/labels/<label_id>/return``, the return label endpoint. """
        return MockHTTPClient(
            url=RETURN_URL,
            method='POST',
            return_json=_label_response(RETURN_LABEL_ID, RETURN_TRACKING_NUMBER, label_format),
        )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _create_sale_order(self, partner=None, products=None):
        return self.env['sale.order'].create({
            'partner_id': (partner or self.us_partner).id,
            'order_line': [
                Command.create({'product_id': product.id})
                for product in (products or (self.product_to_ship1 + self.product_to_ship2))
            ],
        })

    def _get_delivery_wizard(self, sale_order):
        wiz_action = sale_order.action_open_delivery_wizard()
        return self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'carrier_id': self.shipstation.id,
            'order_id': sale_order.id,
        })

    def _validate_picking(self, sale_order):
        """ Confirm the order and validate its delivery, which buys the label. """
        sale_order.action_confirm()
        self.assertGreater(len(sale_order.picking_ids), 0, "The Sales Order did not generate pickings for shipment.")
        picking = sale_order.picking_ids[0]
        self.assertEqual(picking.carrier_id, sale_order.carrier_id, "The carrier is not the same on Picking and on SO.")
        picking.action_assign()
        picking.move_ids.picked = True
        self.assertGreater(picking.weight, 0.0, "The picking weight should be positive.")
        picking._action_done()
        return picking

    def _get_label_attachment_names(self, picking):
        return sorted(picking.message_ids.attachment_ids.mapped('name'))

    def _get_label_attachment_contents(self, picking):
        return sorted(att.raw.to_base64() for att in picking.message_ids.attachment_ids)

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------

    def test_rate_order(self):
        """ Set up a sale order for an US client and ensure that the rate is computed properly. """
        choose_delivery_carrier = self._get_delivery_wizard(self._create_sale_order())

        with self._mock_rates() as rates_mock, self._mock_labels() as labels_mock:
            choose_delivery_carrier.update_price()

        self.assertEqual(choose_delivery_carrier.delivery_price, 12.91)
        rates_mock.assert_called_once()
        labels_mock.assert_not_called()

    def test_rate_order_without_address(self):
        """ Set up a sale order without address and ensure that the rate computation fails. """
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'phone': '(870)-931-0505',
        })
        choose_delivery_carrier = self._get_delivery_wizard(
            self._create_sale_order(partner=partner, products=self.product_to_ship1),
        )

        with self._mock_rates(response=NO_RATES_RESPONSE, status=500) as rates_mock:
            with self.assertRaisesRegex(UserError, 'A shipping carrier error occurred: Missing or Invalid DestinationCountry'):
                choose_delivery_carrier.update_price()

        rates_mock.assert_called_once()

    def test_shipping_order(self):
        """ Ensure that the shipping of an order works properly. """
        sale_order = self._create_sale_order()
        choose_delivery_carrier = self._get_delivery_wizard(sale_order)

        with (
            self._mock_rates() as rates_mock,
            self._mock_labels() as labels_mock,
            self._mock_void() as void_mock,
            self._mock_return() as return_mock,
        ):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            picking = self._validate_picking(sale_order)

        rates_mock.assert_called_once()
        labels_mock.assert_called_once()
        # In production mode, without a return configured, no label is voided nor returned.
        void_mock.assert_not_called()
        return_mock.assert_not_called()

        self.assertEqual(picking.carrier_tracking_ref, TRACKING_NUMBER, "The ShipStation Parcel Reference is not correct.")
        self.assertEqual(picking.shipstation_label_ref, LABEL_ID, "The ShipStation Label Reference is not correct.")

        # Check that the PDF is there with the correct contents.
        self.assertEqual(self._get_label_attachment_contents(picking), [PDF_LABEL_CONTENT])
        self.assertEqual(
            self._get_label_attachment_names(picking),
            [f'LabelShipping-shipstation-{TRACKING_NUMBER}.pdf'],
        )

    def test_shipping_order_zpl_label(self):
        """ Ensure that a ZPL-configured carrier requests and stores a ZPL label. """
        # The 'letter' layout is PDF-only, hence the 4x6 layout.
        self.shipstation.write({
            'shipstation_label_file_type': 'ZPL',
            'shipstation_label_layout': '4x6',
        })
        sale_order = self._create_sale_order()
        choose_delivery_carrier = self._get_delivery_wizard(sale_order)

        with self._mock_rates(), self._mock_labels(label_format='zpl') as labels_mock:
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            picking = self._validate_picking(sale_order)

        labels_mock.assert_called_once()
        payload = json.loads(labels_mock.calls[0].body)
        self.assertEqual(payload['label_format'], 'zpl', "The label format should be requested in ZPL.")
        self.assertEqual(payload['label_layout'], '4x6')
        self.assertEqual(picking.carrier_tracking_ref, TRACKING_NUMBER, "The ShipStation Parcel Reference is not correct.")

        self.assertEqual(
            self._get_label_attachment_names(picking),
            [f'LabelShipping-shipstation-{TRACKING_NUMBER}.zpl'],
            "The label should be attached as a zpl file.",
        )
        self.assertEqual(
            self._get_label_attachment_contents(picking),
            [ZPL_LABEL_CONTENT],
            "The attachment should hold the raw ZPL returned by ShipStation.",
        )

    def test_label_layout_requires_pdf(self):
        """ Ensure that the letter layout is rejected for non-PDF label formats. """
        with self.assertRaises(ValidationError):
            self.shipstation.write({
                'shipstation_label_file_type': 'ZPL',
                'shipstation_label_layout': 'letter',
            })
            self.env.flush_all()

    def test_shipping_order_auto_cancel(self):
        """ Ensure that the shipping of an order works properly and is automatically cancelled during test mode. """
        self.shipstation.prod_environment = False
        sale_order = self._create_sale_order()
        choose_delivery_carrier = self._get_delivery_wizard(sale_order)

        with (
            self._mock_rates() as rates_mock,
            self._mock_labels() as labels_mock,
            self._mock_void() as void_mock,
            self._mock_return() as return_mock,
        ):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            picking = self._validate_picking(sale_order)

        rates_mock.assert_called_once()
        labels_mock.assert_called_once()
        # The label bought outside of production mode is voided right away.
        void_mock.assert_called_once()
        return_mock.assert_not_called()

        self.assertFalse(picking.shipstation_label_ref, "The ShipStation Parcel Reference is still set.")
        self.assertFalse(picking.carrier_tracking_ref, "The tracking number is still set.")

        # Check that the PDF is there with the correct contents.
        self.assertEqual(self._get_label_attachment_contents(picking), [PDF_LABEL_CONTENT])

    def test_shipping_order_auto_return(self):
        """ Ensure that the shipping of an order works properly and is automatically creating returns. """
        self.shipstation.shipstation_supports_returns = True
        self.shipstation.return_label_on_delivery = True
        sale_order = self._create_sale_order()
        choose_delivery_carrier = self._get_delivery_wizard(sale_order)

        with (
            self._mock_rates() as rates_mock,
            self._mock_labels() as labels_mock,
            self._mock_void() as void_mock,
            self._mock_return() as return_mock,
        ):
            choose_delivery_carrier.update_price()
            choose_delivery_carrier.button_confirm()
            picking = self._validate_picking(sale_order)

        rates_mock.assert_called_once()
        labels_mock.assert_called_once()
        # The return label is built from the outgoing label, and nothing is voided.
        return_mock.assert_called_once()
        void_mock.assert_not_called()

        # Check that both labels are there with the correct contents.
        self.assertEqual(
            self._get_label_attachment_names(picking),
            sorted([
                f'LabelShipping-shipstation-{TRACKING_NUMBER}.pdf',
                f'LabelReturn-shipstation-{RETURN_TRACKING_NUMBER}.pdf',
            ]),
            "There should be two labels, one for the shipping and one for the return.",
        )
