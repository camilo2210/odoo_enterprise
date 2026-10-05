from odoo.addons.planning_field_service_sale_timesheet.tests.common import TestPlanningFieldServiceSaleTimesheetCommon


class TestUnderWarrantySubscription(TestPlanningFieldServiceSaleTimesheetCommon):

    def test_under_warranty_keeps_subscription_line_price(self):
        """Under warranty must not zero subscription line prices."""
        subscription_product = self.env['product.product'].create({
            'name': 'Subscription Product',
            'list_price': 100.0,
            'type': 'service',
            'recurring_invoice': True,
            'invoice_policy': 'order',
        })
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
        })
        self.intervention.write({'partner_id': self.partner_1.id, 'sale_order_id': sale_order.id, 'state': '3_in_progress'})
        material_line, subscription_line = self.env['sale.order.line'].create([{
            'order_id': sale_order.id,
            'planning_slot_id': self.intervention.id,
            'product_id': self.consu_product_delivered.id,
            'product_uom_qty': 1,
        }, {
            'order_id': sale_order.id,
            'planning_slot_id': self.intervention.id,
            'product_id': subscription_product.id,
            'product_uom_qty': 1,
        }])

        self.assertEqual(material_line.price_unit, self.consu_product_delivered.list_price)
        self.assertEqual(subscription_line.price_unit, subscription_product.list_price)
        self.assertTrue(subscription_line.recurring_invoice)

        self.intervention.under_warranty = True

        self.assertEqual(material_line.price_unit, 0.0, "Material lines should be zero under warranty")
        self.assertEqual(
            subscription_line.price_unit, subscription_product.list_price,
            "Subscription lines should keep their price when the intervention is under warranty",
        )

    def test_under_warranty_zeros_non_subscription_sale_line(self):
        """Under warranty must also zero the sale order line linked as sale_line_id."""
        non_subscription_product = self.env['product.product'].create({
            'name': 'Non Subscription Service',
            'list_price': 50.0,
            'type': 'service',
            'recurring_invoice': False,
            'invoice_policy': 'order',
        })
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
        })
        service_line, material_line = self.env['sale.order.line'].create([{
            'order_id': sale_order.id,
            'product_id': non_subscription_product.id,
            'product_uom_qty': 1,
        }, {
            'order_id': sale_order.id,
            'planning_slot_id': self.intervention.id,
            'product_id': self.consu_product_delivered.id,
            'product_uom_qty': 1,
        }])
        self.intervention.write({
            'partner_id': self.partner_1.id,
            'sale_order_id': sale_order.id,
            'sale_line_id': service_line.id,
            'state': '3_in_progress',
        })
        self.assertFalse(service_line.planning_slot_id)

        self.intervention.under_warranty = True

        self.assertEqual(service_line.price_unit, 0.0)
        self.assertEqual(material_line.price_unit, 0.0)
