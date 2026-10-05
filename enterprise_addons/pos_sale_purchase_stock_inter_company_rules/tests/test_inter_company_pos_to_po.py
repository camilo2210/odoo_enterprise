from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.addons.sale_purchase_stock_inter_company_rules.tests.common import TestInterCompanyRulesCommonStock


@tagged('post_install', '-at_install')
class TestInterCompanyPosToPurchaseWithStock(TestInterCompanyRulesCommonStock, CommonPosTest):

    def test_10_inter_company_purchase_order_from_pos_with_custom_attribute_values(self):
        """
        Check that the custom attribute values are transfered by procurements, when origin
        document is pos
        """
        self.company_b.intercompany_generate_sales_orders = True
        warehouse_a = self.env['stock.warehouse'].search([('company_id', '=', self.company_a.id)], limit=1)
        warehouse_a.delivery_steps = 'pick_pack_ship'
        mto_route = warehouse_a.mto_pull_id.route_id
        mto_route.rule_ids.procure_method = "make_to_order"
        mto_route.active = True
        buy_route = warehouse_a.buy_pull_id.route_id
        buy_route.product_selectable = True

        # setup product with customizable attribute value
        product_attribute = self.env['product.attribute'].create({
            'name': 'Fabrics',
            'display_type': 'radio',
            'create_variant': 'no_variant',
            'value_ids': [
                Command.create({'name': 'Leather'}),
                Command.create({'name': 'Custom', 'is_custom': True}),
            ]
        })

        product_storable = self.env['product.template'].create({
            'name': 'Storable',
            'is_storable': True,
            'available_in_pos': True,
            'route_ids': [Command.set([buy_route.id, mto_route.id])],
            'company_id': False,
            'seller_ids': [
                Command.create({
                    'partner_id': self.company_b.partner_id.id,
                    'min_qty': 1,
                    'price': 250,
                    'company_id': self.company_a.id,
                }),
            ],
            'attribute_line_ids': [
                Command.create({
                    'attribute_id': product_attribute.id,
                    'value_ids': [Command.set(product_attribute.value_ids.ids)]
                })
            ],
        })
        ptavs = self.env["product.template.attribute.value"].search(
            [("product_attribute_value_id", "in", product_attribute.value_ids.ids)]
        ).sorted("id")

        self.pos_config_usd.open_ui()
        custom_value = "Test Instructions"

        order_data = {
            "company_id": self.env.company.id,
            "session_id": self.pos_config_usd.current_session_id.id,
            "partner_id": self.partner.id,
            "lines": [Command.create({
                        "name": "OL/0001",
                        "product_id": product_storable.product_variant_id.id,
                        "price_unit": 10,
                        "attribute_value_ids": [ptavs[1].id],
                        "custom_attribute_value_ids": [Command.create({
                            'custom_product_template_attribute_value_id': ptavs[1].id,
                            'custom_value': custom_value,
                        })],
                        "full_product_name": f"Storable (Fabrics: Custom: {custom_value})",
                        "qty": 2,
                        "tax_ids": [[6, False, []]],
                        "price_subtotal": 20,
                        "price_subtotal_incl": 20,
                        "total_cost": 20,
                    })],
            'payment_ids': [Command.create({
                'amount': 20,
                'name': fields.Datetime.now(),
                'payment_method_id': self.cash_payment_method.id
            })],
            "amount_paid": 20.0,
            "amount_total": 20.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "shipping_date": fields.Date.today(),
        }
        pos_order_id = self.env["pos.order"].sync_from_ui([order_data])['pos.order'][0]['id']
        pos_order = self.env["pos.order"].search([('id', '=', pos_order_id)])

        po = self.env['purchase.order'].search([('partner_id', '=', self.company_b.partner_id.id)])
        self.assertTrue(custom_value in po.order_line.display_name)
        po.with_company(self.company_a).button_confirm()

        auto_generated_so = self.env['sale.order'].search([('partner_id', '=', self.company_a.partner_id.id)])
        self.assertRecordValues(auto_generated_so, [{'auto_generated': True, 'auto_purchase_order_id': po.id}])
        self.assertTrue(custom_value in auto_generated_so.order_line.name)
        original_custom_attribute = pos_order.lines.custom_attribute_value_ids
        copied_custom_attribute = auto_generated_so.order_line.product_custom_attribute_value_ids
        self.assertEqual(
            original_custom_attribute.custom_value,
            copied_custom_attribute.custom_value,
        )
        self.assertEqual(
            original_custom_attribute.custom_product_template_attribute_value_id,
            copied_custom_attribute.custom_product_template_attribute_value_id,
        )
