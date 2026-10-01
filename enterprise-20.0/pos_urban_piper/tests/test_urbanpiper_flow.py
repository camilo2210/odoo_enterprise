# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import Command
from odoo.tests import tagged

from ..utils.urbanpiper_connector import UrbanPiperConnector
from odoo.addons.pos_urban_piper.tests.common import CommonPosUrbanPiperTest


@tagged('post_install', '-at_install')
class TestUrbanPiperFlow(CommonPosUrbanPiperTest):
    _test_user_groups = None  # FIXME list needed groups

    def test_multi_branch_tax_setup(self):
        self.parent_company = self.company_data['company']
        self.child_company = self.env['res.company'].create({
            'name': 'Branch Company',
            'parent_id': self.parent_company.id,
            'chart_template': self.env.company.chart_template,
            'country_id': self.env.company.country_id.id,
        })
        bank_payment_method = self.bank_payment_method.copy()
        bank_payment_method.company_id = self.child_company.id
        self.tax_15.write({
            'company_id': self.parent_company.id,
        })
        self.tax_group.write({
            'company_id': self.parent_company.id,
        })
        self.product_with_tax_15 = self.env['product.template'].create({
            'name': 'Product 1',
            'available_in_pos': True,
            'taxes_id': [(4, self.tax_15.id)],
            'type': 'consu',
            'list_price': 100.0,
        })
        self.child_branch_pos_config = self.env['pos.config'].with_company(self.child_company).create({
            'name': 'Branch POS',
            'journal_id': self.company_data['default_journal_sale'].id,
            'payment_method_ids': [(4, bank_payment_method.id)],
        })
        doordash = self.env.ref('pos_urban_piper.pos_delivery_provider_doordash')
        self.child_branch_store = self.env['pos.urbanpiper.store'].with_company(self.child_company).create({
            'name': 'Little UrbanPiper Branch Store',
            'aggregator_lines': [Command.create({'delivery_provider_id': doordash.id})],
            'urbanpiper_apikey': 'demo',
            'urbanpiper_username': 'demo',
            'city': 'Gandhinagar',
            'config_id': self.child_branch_pos_config.id
        })
        self.child_branch_pos_config.open_ui()
        order = self.create_urbanpiper_order(
            product=self.product_with_tax_15,
            qty=5,
            packaging_charge=50,
            delivery_charge=100,
            discount_amount=150,
            provider=doordash,
            context={'store_id': self.child_branch_store.id},
        )
        order.order_status_update('Food Ready')
        self.assertEqual(self.tax_15.id, order.lines[0].tax_ids.id)

    def test_product_taxes(self):
        self.tax_15.original_tax_ids = [(4, self.tax_15.id)]
        self.product_1.sudo().taxes_id = [(4, self.tax_15.id)]
        packaging_product = self.env.ref('pos_urban_piper.product_packaging_charges', False)
        delivery_product = self.env.ref('pos_urban_piper.product_delivery_charges', False)
        packaging_product.taxes_id = [(6, 0, self.tax_15.ids)]
        self.discount_product = self.env.ref('pos_discount.product_product_consumable', False)
        self.discount_product.taxes_id = [(6, 0, self.tax_15.ids)]
        delivery_product.taxes_id = [(5, 0, 0)]
        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order(
            qty=2,
            packaging_charge=10,
            delivery_charge=10,
            discount_amount=10,
            context={'has_tax': False},
        )
        self.assertEqual(order.lines[0].tax_ids.id, self.tax_15.id)
        self.assertEqual(order.lines[1].tax_ids.id, self.tax_15.id)
        self.assertEqual(order.lines[2].tax_ids.id, False)
        self.assertEqual(order.lines[3].tax_ids.id, self.tax_15.id)

    def test_inclusive_tax_type_with_normal_order_line(self):
        self.tax_15 = self.env['account.tax'].create({
            'name': '15% VAT Inclusive',
            'amount': 15,
            'amount_type': 'percent',
            'price_include_override': 'tax_included',
        })
        self.product_1.taxes_id = [(6, 0, self.tax_15.ids)]
        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order(qty=2, context={'has_tax': False})
        line = order.lines[0]
        self.assertEqual(line.tax_ids.id, self.tax_15.id)
        self.assertAlmostEqual(line.price_unit, 100.0, places=2)
        self.assertAlmostEqual(line.price_subtotal, 173.91, places=2)
        self.assertAlmostEqual(line.price_subtotal_incl, 200.0, places=2)

    def test_charges_sent_to_urbanpiper(self):
        delivery_charge_product = self.env.ref('pos_urban_piper.product_delivery_charges')
        delivery_charge_product.list_price = 10
        charges_data = self.env['product.template']._prepare_urbanpiper_charges_data(self.urbanpiper_store)
        self.assertEqual(
            charges_data,
            [{'code': 'DC_F', 'title': 'Delivery Charges', 'active': True, 'structure': {'applicable_on': 'order.order_subtotal', 'value': 10.0}, 'item_ref_ids': ['all']}]
        )

    def test_order_with_no_children_taxes(self):
        tax = self.env['account.tax'].create({
            'name': 'Tax without children taxes',
            'amount_type': 'group',
        })
        self.product_1.write({
            'taxes_id': [Command.set([tax.id])],
        })

        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order()

        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines[0].price_unit, 100.0)
        self.assertEqual(order.lines[0].price_subtotal, 100.0)
        self.assertEqual(order.amount_total, 100.0)
        self.assertEqual(order.amount_tax, 0.0)

    def test_paid_future_order_creates_session_account_move(self):
        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order(context={'delivery_datetime': 30})
        order.order_status_update('Food Ready')
        session = self.urban_piper_config.current_session_id
        session.close_session_from_ui()
        self.assertEqual(len(session.move_ids), 1)
        self.assertTrue(order.preset_time)

    def test_order_cancellation_status(self):
        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order(product=self.product_1, qty=1)
        self.env['pos.prep.order'].update_last_order_change(order)
        order.process_urbanpiper_order_status_update({
            'order_id': 'order-to-cancel',
            'new_state': 'Cancelled',
            'store_id': self.urbanpiper_store.store_identifier,
            'message': 'late delivery',
        }, self.urbanpiper_store)
        self.assertEqual(order.delivery_status, 'cancelled')
        self.assertEqual(order.state, 'cancel')
        self.assertIn('order cancelled due to late delivery', order.message_ids[0].body.lower())
        prep_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)])
        prep_line = prep_order.prep_line_ids
        self.assertEqual(len(prep_line), 1)
        self.assertEqual(prep_line.quantity, 1)
        self.assertEqual(prep_line.cancelled, 1)
        # Test online order cancellation from frontend with a reason
        order_2 = self.create_urbanpiper_order()
        # Simulate the frontend cancellation flow by calling
        # `order_status_update` directly with a cancellation reason in the context.
        order_2.with_context(cancellation_reason='Product is out of Stock', cancelled_by='Popatlal').order_status_update('Cancelled', 'item_out_of_stock')
        self.assertIn('order cancelled by popatlal due to product is out of stock', order_2.message_ids[0].body.lower())

    def test_category_image_url_payload(self):
        category = self.env['pos.category'].create({'name': 'Test Category', 'sequence': 21})

        category_data = category._prepare_urbanpiper_data(self.urban_piper_config)
        self.assertEqual(len(category_data), 1)
        self.assertEqual(category_data[0]['name'], 'Test Category')
        self.assertEqual(category_data[0]['sort_order'], 21)
        self.assertFalse('img_url' in category_data[0])

        image = """<svg height='180' width='180'>
            <rect width="180" height="180" style="fill: #FF5F1F;" />
            <text fill='#EEE' font-size='96' text-anchor='middle' x='90' y='125'>P</text>
        </svg>"""
        category.image_128 = base64.b64encode(image.encode()).decode()
        category_data = category._prepare_urbanpiper_data(self.urban_piper_config)

        self.assertEqual(len(category_data), 1)
        self.assertEqual(category_data[0]['name'], 'Test Category')
        self.assertTrue('img_url' in category_data[0])
        web_base_url = self.env['ir.config_parameter'].get_str('web.base.url')
        self.assertIn(web_base_url + '/web/image/', category_data[0]['img_url'])

    def test_urbanpiper_store_tax_type(self):
        tax_5 = self.env['account.tax'].create({
            'name': '5% VAT',
            'amount': 5,
            'amount_type': 'percent',
        })
        self.product_1.write({
            'taxes_id': [(4, tax_5.id)],
        })

        self.urbanpiper_store.tax_type = 'total_included'
        item_data = self.product_1._prepare_urbanpiper_data(self.urbanpiper_store)
        taxes_data = self.product_1._prepare_urbanpiper_taxes_data(self.urbanpiper_store)
        self.assertEqual(len(item_data), 1)
        self.assertEqual(item_data[0]['price'], 105.00)
        self.assertEqual(len(taxes_data), 0)

        self.urbanpiper_store.tax_type = 'total_excluded'
        item_data = self.product_1._prepare_urbanpiper_data(self.urbanpiper_store)
        taxes_data = self.product_1._prepare_urbanpiper_taxes_data(self.urbanpiper_store)
        self.assertEqual(len(item_data), 1)
        self.assertEqual(item_data[0]['price'], 100.00)
        self.assertEqual(len(taxes_data), 1)

    def test_urbanpiper_store_platform_pricing(self):
        fixed_pricelist = self.env['product.pricelist'].create({
            'name': 'Fixed',
            'item_ids': [Command.create({
                'compute_price': 'fixed',
                'fixed_price': 150,
            })],
        })
        self.urbanpiper_store.aggregator_lines[0].pricelist_id = fixed_pricelist
        item_data_lst = self.product_1._prepare_urbanpiper_data(self.urbanpiper_store)
        self.assertEqual(len(item_data_lst), 1)
        item_data = item_data_lst[0]
        self.assertEqual(item_data['price'], 100.00)
        self.assertEqual(len(item_data['platform_pricing']), 1)
        self.assertEqual(item_data['platform_pricing'][0]['platform'], 'justeat')
        self.assertEqual(item_data['platform_pricing'][0]['price'], 150)

    def test_post_stores_payload(self):
        self.env['res.lang']._activate_lang('hi_IN')
        resource_calendar = self.env['resource.calendar'].create({
            'name': 'Delivery Timings',
            'attendance_ids': [
                Command.create({'dayofweek': '0', 'hour_from': 0, 'hour_to': 23.99}),
                Command.create({'dayofweek': '1', 'hour_from': 10, 'hour_to': 20}),
            ],
        })
        preset = self.env['pos.preset'].create({
            'name': 'Test Delivery Preset',
            'identification': 'online',
            'use_timing': True,
            'resource_calendar_id': resource_calendar.id
        })
        self.urbanpiper_store.preset_id = preset
        self.urbanpiper_store.with_context(lang='hi_IN').name = "गडा इलेक्ट्रॉनिक्स"

        with self.capture_request_payloads() as payloads:
            UrbanPiperConnector(self.urbanpiper_store).post_stores()

        self.assertEqual(len(payloads[0]['stores']), 1)
        self.assertEqual(payloads[0]['stores'][0], {
            'name': 'Very Special UrbanPiper Store',
            'city': 'Ahmedabad',
            'ref_id': 'very-special-store',
            'min_pickup_time': 1200,
            'translations': [{'language': 'hi', 'name': 'गडा इलेक्ट्रॉनिक्स'}],
            'timings': [{
                'day': 'monday',
                'slots': [{'start_time': '00:00:00', 'end_time': '23:59:00'}]
            }, {
                'day': 'tuesday',
                'slots': [{'start_time': '10:00:00', 'end_time': '20:00:00'}]
            }]
        })

    def test_post_location_inventory_payload(self):
        self.env['product.template'].search([]).urbanpiper_store_ids = False
        self.env['res.lang']._activate_lang('hi_IN')
        doordash = self.env.ref('pos_urban_piper.pos_delivery_provider_doordash')
        self.urbanpiper_store.aggregator_lines = [Command.create({'delivery_provider_id': doordash.id})]
        self.product.with_context(lang='hi_IN').write({
            'urbanpiper_store_ids': [Command.link(self.urbanpiper_store.id)],
            'name': 'पिज़ो',
            'urbanpiper_meal_type': '1',
            'is_recommended_on_urbanpiper': True,
            'is_alcoholic_on_urbanpiper': True,
            'taxes_id': [(5, 0, 0), (4, self.tax_15.id)],
            'list_price': 200,
        })
        self.product.urbanpiper_pos_platform_ids = [Command.link(doordash.id)]

        delivery_charge_product = self.env.ref('pos_urban_piper.product_delivery_charges')
        delivery_charge_product.list_price = 10

        with self.capture_request_payloads() as payloads:
            UrbanPiperConnector(self.urbanpiper_store).post_location_inventory()

        def assert_payload_equal(data, expected_values):
            data_payload = {
                key: data[key]
                for key in expected_values
            }
            self.assertDictEqual(data_payload, expected_values)

        inventory_payload = payloads[0]
        self.assertIsNotNone(inventory_payload)
        # Items
        self.assertEqual(len(inventory_payload['items']), 1)
        assert_payload_equal(inventory_payload['items'][0], {
            'title': 'Pizza',
            'price': 230.0,
            'food_type': '1',
            'ref_id': str(self.product.id),
            'category_ref_ids': [str(self.category.id)],
            'available': True,
            'recommended': True,
            'included_platforms': ['doordash'],
            'tags': {'default': [], 'doordash': ['alcohol-present']},
            'translations': [{'language': 'hi', 'title': 'पिज़ो'}],
        })
        # Taxes - No taxes data when tax_type = total_included
        self.assertEqual(len(inventory_payload['taxes']), 0)
        # Category
        self.assertEqual(len(inventory_payload['categories']), 1)
        assert_payload_equal(inventory_payload['categories'][0], {
            'name': 'Test Category',
            'ref_id': str(self.category.id),
            'active': True,
        })
        self.assertNotIn('img_url', inventory_payload['categories'][0])
        # Charges
        self.assertEqual(len(inventory_payload['charges']), 1)
        assert_payload_equal(inventory_payload['charges'][0], {
            'code': 'DC_F',
            'title': 'Delivery Charges',
            'active': True,
            'item_ref_ids': ['all'],
            'structure': {
                'applicable_on': 'order.order_subtotal',
                'value': 10.0
            },
        })

        self.assertEqual(len(inventory_payload['options']), 5)
        self.assertEqual(len(inventory_payload['option_groups']), 2)

        # payload with total_excluded as tax type
        self.urbanpiper_store.tax_type = 'total_excluded'
        with self.capture_request_payloads() as payloads:
            UrbanPiperConnector(self.urbanpiper_store).post_location_inventory()
        inventory_payload = payloads[0]
        self.assertEqual(len(inventory_payload['taxes']), 1)
        assert_payload_equal(inventory_payload['taxes'][0], {
            'code': 'ST_P',
            'title': 'Sales Tax',
            'active': True,
            'item_ref_ids': [str(self.product.id)],
            'structure': {
                'value': 15.0
            },
        })
        self.assertEqual(inventory_payload['items'][0]['price'], 200)
