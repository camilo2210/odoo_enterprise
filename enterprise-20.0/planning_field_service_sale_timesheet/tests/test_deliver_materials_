# Part of Odoo. See LICENSE file for full copyright and licensing details

from .common import TestPlanningFieldServiceSaleTimesheetCommon


class TestDeliverMaterialsWhenTaskDone(TestPlanningFieldServiceSaleTimesheetCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'project_id' in cls.intervention._fields:
            cls.intervention.project_id = cls.field_service_project
        else:
            cls.env['res.config.settings'].create({'planning_project_id': cls.field_service_project.id}).execute()
        cls.consu_product = cls.env['product.product'].create({
            'name': 'Consommable product',
            'list_price': 40,
            'type': 'consu',
            'invoice_policy': 'delivery',
        })

        cls.service_product = cls.env['product.product'].create({
            'name': "Service Ordered, create task in fsm",
            'standard_price': 30,
            'list_price': 90,
            'type': 'service',
            'invoice_policy': 'delivery',
            'service_type': 'milestones',
            'service_tracking': 'task_global_project',
            'project_id': cls.field_service_project.id,
        })

    def test_deliver_materials_when_intervention_done(self):
        """ Test system automatically updates materials when intervention is done.

            Test Case:
            =========
            1) Add some materials, only the qty_delivered is empty (equal to 0)
            2) Mark the intervention as done
            3) Check if qty_delivered for each SOL contain material of the intervention is updated and equal to the product_uom_qty.
        """
        self.intervention.resource_ids = self.george_employee.resource_id
        self.intervention.state = '3_in_progress'
        self.assertFalse(self.intervention.material_line_product_count, "No product should be linked to a new intervention.")
        self.intervention.write({'partner_id': self.partner_1.id})
        self.intervention.with_user(self.george_user).action_view_material()
        self.consu_product.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).set_fsm_quantity(5)
        self.assertEqual(self.intervention.material_line_product_count, 5, "5 products should be linked to the intervention")

        product_sol = self.intervention.sale_order_id.order_line.filtered(lambda sol: sol.product_id == self.consu_product)
        self.assertEqual(product_sol.product_uom_qty, 5, "The quantity of this product should be equal to 5.")

        self.intervention.action_complete()
        self.assertEqual(self.intervention.state, '4_completed', 'The intervention should be completed.')
        self.assertEqual(product_sol.qty_delivered, product_sol.product_uom_qty, 'The delivered quantity for the ordered product should be updated when the intervention is marked as done.')

    def test_milestone_service_product_delivery_when_intervention_done(self):
        """ Test system doesn't automatically updates delivered quantities
            for milestone service products when intervention is done.
            Instead, it's computed based on reached milestones.

            Test Case:
            =========
            1) Add service product with invoice policy 'milestone'
            2) Mark the intervention as done
            3) Check if qty_delivered for SOL is still 0. (no milestone is created yet)
            4) Create a milestone with quantity 50%
            5) Check if qty_delivered for SOL is updated to 0.5.
        """
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']

        sale_order = SaleOrder.create({
            'partner_id': self.partner_1.id,
            'partner_invoice_id': self.partner_1.id,
            'partner_shipping_id': self.partner_1.id,
        })

        sale_order_line = SaleOrderLine.create({
            'product_id': self.product_milestone.id,
            'product_uom_qty': 4,
            'order_id': sale_order.id,
        })

        sale_order.action_confirm()
        self.intervention.state = '3_in_progress'
        self.intervention.sale_line_id = sale_order_line

        self.intervention.action_complete()
        self.assertEqual(self.intervention.state, '4_completed', 'The intervention should be mark as completed')
        self.assertEqual(sale_order_line.qty_delivered, 0, 'The delivered quantity should remain 0 as no milestone is created yet.')

        milestone = self.env['project.milestone'].create({
            'name': 'Test Milestone',
            'sale_line_id': sale_order_line.id,
            'quantity_percentage': 0.5,
            'is_reached': False,
            'project_id': self.field_service_project.id,
        })
        self.assertEqual(sale_order_line.qty_delivered, 0, 'The delivered quantity should remain 0 as the milestone is not reached yet.')

        milestone.is_reached = True
        self.assertEqual(sale_order_line.qty_delivered, 2, 'The delivered quantity should be updated to 2 as the milestone with 50% of quantity percentage is reached.')
