# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.addons.planning_field_service_sale_timesheet.tests.common import TestPlanningFieldServiceSaleTimesheetCommon
from odoo.exceptions import UserError


class TestPlanningFieldServiceSaleTimesheetWithStock(TestPlanningFieldServiceSaleTimesheetCommon):
    """
        The sale flow is tested here because when the stock module is installed, its behavior is modified. To ensure the behavior still works without the stock module, a test is run
        at-install on the planning_field_service_sale_timesheet module
    """
    _test_user_groups = None  # FIXME list needed groups

    def test_field_service_flow(self):
        """
        Test Cases:
        ==========
        1) Add intervention (planning.slot) and Assert no products added
        2) Add and remove different quantities of products:
            - Service (order/delivered)
            - Consumable (order/delivered)
            And assert after each operation on product count
        3) Set product quantity after confirming SO
        """
        self.intervention.state = '3_in_progress'
        self.intervention.partner_id = False
        self.assertFalse(self.intervention.material_line_product_count, "No product should be linked to a new intervention")
        with self.assertRaises(UserError, msg='Should not be able to get to material without customer set'):
            self.intervention.action_view_material()
        self.intervention.write({'partner_id': self.partner_1.id, 'resource_ids': self.henri_employee.resource_id.ids})
        self.set_field_service_project(self.field_service_project, self.intervention)
        self.intervention.with_user(self.project_user).action_view_material()

        expected_product_count = 1
        self.service_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.service_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.consu_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.consu_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count -= 1
        self.consu_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_remove_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count += 1
        self.service_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        quantity_to_add = 5
        expected_product_count += quantity_to_add
        self.consu_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).set_fsm_quantity(quantity_to_add)
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        # validation and SO
        self.assertNotEqual(self.intervention.state, '4_completed', "Intervention should not be marked as done")
        self.assertEqual(len(self.intervention.sale_order_id.order_line), 4)

        order_line = self.intervention.sale_order_id.order_line.filtered(
            lambda sol: sol.product_id == self.service_product_ordered
        )
        self.assertEqual(order_line.product_uom_qty, 1)
        self.assertFalse(self.intervention.intervention_timesheet_ids)
        self.intervention.with_user(self.henri_user).action_complete()
        self.assertEqual(self.intervention.state, '4_completed', "Intervention should be completed")
        self.assertEqual(self.intervention.sale_order_id.state, 'sale', "Sale order should be confirmed")
        self.assertEqual(len(self.intervention.intervention_timesheet_ids), 1, "One timesheet should be generated once the intervention has been completed")
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention (the timesheet should not be taken into account)")

        # Add product quantity after confirming the SO
        self.service_product_ordered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).set_fsm_quantity(9)
        self.assertEqual(order_line.product_uom_qty, 9)
        expected_product_count += 8
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")
