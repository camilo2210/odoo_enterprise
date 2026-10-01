# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

import odoo.tests

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.addons.pos_urban_piper.tests.common import CommonPosUrbanPiperTest


@odoo.tests.tagged('post_install', '-at_install')
class TestFrontendUrbanPiper(CommonPosUrbanPiperTest, TestPointOfSaleHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_01_order_flow(self):
        self.urban_piper_config.open_ui()
        order_1 = self.create_urbanpiper_order(is_instant_order=True)
        order_2 = self.create_urbanpiper_order(product=self.product_2)
        self.create_urbanpiper_order(qty=2, product=self.product_2)
        self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [(4, self.urban_piper_config.id)],
        })
        PosOrder = self.env.registry.models['pos.order']

        def mark_urbanpiper_prep_order_as_printed_patch(self):
            # Catch the intentionally raised ValueError from the mathod
            # and return 'False' instead of propagating the exception
            try:
                return super(PosOrder, self).mark_urbanpiper_prep_order_as_printed()
            except ValueError:
                return False
        with patch.object(PosOrder, "mark_urbanpiper_prep_order_as_printed", mark_urbanpiper_prep_order_as_printed_patch):
            self.start_pos_tour('OrderFlowTour', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual(100.0, order_1.amount_total)
        self.assertEqual(100.0, order_1.amount_paid)
        self.assertEqual(0.0, order_1.amount_difference)
        self.assertEqual(0.0, order_1.amount_tax)
        self.assertEqual(100.0, order_1.payment_ids[0].amount)
        # Check if order is quick order or not
        is_instant_order_1 = json.loads(order_1.delivery_json).get("order", {}).get("details", {}).get("ext_platforms", [{}])[0].get("extras", {}).get("is_instant_order", False)
        self.assertEqual(True, is_instant_order_1)
        self.assertEqual(200.0, order_2.amount_total)
        self.assertEqual(200.0, order_2.amount_paid)
        self.assertEqual(0.0, order_2.amount_difference)
        self.assertEqual(0.0, order_2.amount_tax)
        self.assertEqual(200.0, order_2.payment_ids[0].amount)
        is_instant_order_2 = json.loads(order_2.delivery_json).get("order", {}).get("details", {}).get("ext_platforms", [{}])[0].get("extras", {}).get("is_instant_order", False)
        self.assertEqual(False, is_instant_order_2)
        pdis_order1 = self.env['pos.prep.order'].search([('pos_order_id', '=', order_1.id)], limit=1)
        pdis_order2 = self.env['pos.prep.order'].search([('pos_order_id', '=', order_2.id)], limit=1)
        self.assertEqual(len(pdis_order1.prep_line_ids), 1, "Should have 1 preparation orderlines")
        self.assertEqual(len(pdis_order2.prep_line_ids), 1, "Should have 1 preparation orderlines")

        # Test ticket generation
        html = order_1.order_receipt_generate_html()
        self.assertTrue(order_1.delivery_provider_id.name in html)
        delivery_code = json.loads(order_1.delivery_json)['order']['details']['ext_platforms'][0]['id']
        first_part = delivery_code[:-4]
        last_part = delivery_code[-4:]
        self.assertTrue(first_part in html)
        self.assertTrue(last_part in html)

    def test_02_order_with_instruction(self):
        self.urban_piper_config.open_ui()
        order_1 = self.create_urbanpiper_order(qty=4, delivery_instruction='Make it spicy..')
        self.start_pos_tour('OrderWithInstructionTour', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual(400.0, order_1.amount_total)
        self.assertEqual(400.0, order_1.amount_paid)
        self.assertEqual(0.0, order_1.amount_tax)
        self.assertEqual(400.0, order_1.payment_ids[0].amount)
        self.assertEqual('Make it spicy..', order_1.general_customer_note)

    def test_03_order_with_charges_and_discount(self):
        self.urban_piper_config.open_ui()
        order_1 = self.create_urbanpiper_order(qty=5, packaging_charge=50, delivery_charge=100, discount_amount=150)
        self.start_pos_tour('OrderWithChargesAndDiscountTour', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual(500, order_1.amount_total)
        self.assertEqual(500, order_1.amount_paid)
        self.assertEqual(0, order_1.amount_tax)
        self.assertEqual(500, order_1.payment_ids[0].amount)

    def test_reject_order(self):
        self.urban_piper_config.open_ui()
        self.create_urbanpiper_order(qty=5, packaging_charge=50, delivery_charge=100, discount_amount=150)
        self.start_pos_tour('test_reject_order', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual("cancelled", self.urban_piper_config.current_session_id.order_ids[0].delivery_status)

    def test_order_prep_time(self):
        self.urban_piper_config.open_ui()
        order_1 = self.create_urbanpiper_order(qty=5, packaging_charge=50, delivery_charge=100, discount_amount=150)
        self.start_pos_tour('OrderPrepTime', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual(35, order_1.prep_time)

    def test_payment_method_close_session(self):
        self.urban_piper_config.payment_method_ids = self.env['pos.payment.method'].search([]).filtered(lambda pm: pm.type == 'bank')
        self.urban_piper_config.with_user(self.pos_admin).open_ui()
        self.start_pos_tour('test_payment_method_close_session', pos_config=self.urban_piper_config, login="pos_admin")

    def test_urban_piper_orders_filter_button(self):
        self.urban_piper_config.open_ui()
        self.create_urbanpiper_order()
        self.start_pos_tour('test_urban_piper_orders_filter_button', pos_config=self.urban_piper_config, login="pos_admin")

    def test_dynamic_product_variant_creation(self):
        self.urban_piper_config.open_ui()
        ptav_ids = self.product_tmpl.attribute_line_ids.product_template_value_ids.ids
        order = self.create_urbanpiper_order(product=self.product_tmpl, qty=2, ptav_ids=[(6, 0, [ptav_ids[0], ptav_ids[3]])])
        self.start_pos_tour('test_dynamic_product_variant_creation', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual(len(order.lines), 1, "There should be only one order line")
        self.assertEqual(len(self.product_tmpl.product_variant_ids), 1, "There should be only one variant created")
        self.assertEqual(order.lines[0].product_id.id, self.product_tmpl.product_variant_ids[0].id, "The product should be the created variant")

    def test_dynamic_with_never_create_variant_attribute(self):
        self.product_tmpl.attribute_line_ids = [
            (0, 0, {
                'attribute_id': self.attribute_material.id,
                'value_ids': [(6, 0, self.attribute_material.value_ids.ids)],
            }),
        ]
        self.urban_piper_config.open_ui()
        ptav_ids = self.product_tmpl.attribute_line_ids.product_template_value_ids.ids
        order = self.create_urbanpiper_order(product=self.product_tmpl, qty=2, ptav_ids=[(6, 0, [ptav_ids[0], ptav_ids[3], ptav_ids[4]])])
        self.start_pos_tour('test_dynamic_with_never_create_variant_attribute', pos_config=self.urban_piper_config, login="pos_admin")
        self.assertEqual(len(order.lines), 1, "There should be only one order line")
        self.assertEqual(len(self.product_tmpl.product_variant_ids), 1, "There should be only one variant created")
        self.assertEqual(order.lines[0].product_id.id, self.product_tmpl.product_variant_ids[0].id, "The product should be the created variant")

    def test_to_check_attribute(self):
        self.configurable_chair.active = True
        self.urban_piper_config.open_ui()
        ptav_ids = self.configurable_chair.attribute_line_ids.product_template_value_ids.ids
        self.create_urbanpiper_order(product=self.configurable_chair, qty=2, ptav_ids=[(6, 0, [ptav_ids[0], ptav_ids[2], ptav_ids[5], ptav_ids[7], ptav_ids[8]])])
        self.start_pos_tour('test_to_check_attribute', pos_config=self.urban_piper_config, login="pos_admin")

    def test_product_level_discount(self):
        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order(qty=2, line_discount=40)
        self.start_pos_tour('test_product_level_discount', pos_config=self.urban_piper_config, login='pos_admin')
        self.assertEqual(160.0, order.amount_total)
        self.assertEqual(160.0, order.amount_paid)
        self.assertEqual('paid', order.state)
        self.assertEqual(20, order.lines[0].discount)
