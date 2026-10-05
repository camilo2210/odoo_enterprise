# Part of Odoo. See LICENSE file for full copyright and licensing details

from .common import TestPlanningFieldServiceSaleTimesheetCommon
from odoo.exceptions import UserError
from odoo.tests import new_test_user


class TestFsmFlowSaleAtInstall(TestPlanningFieldServiceSaleTimesheetCommon):
    """
    When the 'planning_field_service_stock' module is installed, it updates the behavior
    of the SO linked to intervention by forcing those SO to be in a confirmed state.
    Since service product can be removed from a intervention only if the SO linked is in
    a draft state, the stock module prevent this behavior. Therefore, the tag 'at_install' is
    not removed from this class in order to ensure adding/removing product from a task
    works both when the stock module is installed and when it is not.
    """
    _test_user_groups = None  # FIXME list needed groups

    def test_fsm_flow(self):
        """
        Test Cases:
        ==========
        1) Add intervention and Assert no products added
        2) Add and remove different quantities of products:
            - Service (order/delivered)
            - Consumable (order/delivered)
            And assert after each operation on product count
        3) Set product quantity after confirming SO
        """
        if self.env['ir.module.module']._get("planning_field_service_sale_stock").state == 'installed':
            self.skipTest('This test will fail if planning_field_service_stock is installed since the behavior is altered.')
        self.env['res.config.settings'].create({'group_product_pricelist': True}).execute()
        self.intervention.write({
            'state': '3_in_progress',
            'resource_ids': self.henri_employee.resource_id.ids,
            'partner_id': False,
        })

        if not self.env.company.chart_template:
            self.env["account.chart.template"].try_loading('generic_coa', self.env.company)

        self.assertFalse(self.intervention.material_line_product_count, "No product should be linked to a new intervention")
        with self.assertRaises(UserError, msg='Should not be able to get to material without customer set'):
            self.intervention.action_view_material()
        self.intervention.write({'partner_id': self.partner_1.id})
        self.intervention.with_user(self.henri_user).action_view_material()

        expected_product_count = 1
        self.service_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        expected_product_count -= 1
        self.service_product_delivered.with_user(self.henri_user).with_context({'intervention_id': self.intervention.id}).fsm_remove_quantity()
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
        self.assertNotEqual(self.intervention.state, '4_completed', "Intervention should not be completed")
        self.assertEqual(len(self.intervention.sale_order_id.order_line), 4)

        order_line = self.intervention.sale_order_id.order_line.filtered(
            lambda l: l.product_id == self.service_product_ordered
        )
        self.assertEqual(order_line.product_uom_qty, 1)
        self.intervention.action_complete()
        self.assertEqual(self.intervention.state, '4_completed', "Intervention should be completed")
        self.assertEqual(self.intervention.sale_order_id.state, 'sale', "Sale order should be confirmed")

        # Add product quantity after confirming the SO
        self.service_product_ordered.with_context({'intervention_id': self.intervention.id}).set_fsm_quantity(9)
        self.assertEqual(order_line.product_uom_qty, 9)
        expected_product_count += 8
        self.assertEqual(self.intervention.material_line_product_count, expected_product_count, f"{expected_product_count} product should be linked to the intervention")

        # quotation
        self.assertEqual(self.intervention.quotations_count, 0, "0 quotation should be linked to the intervention since we don't create a quotation via the Create Quotation button.")
        quotation_context = self.intervention.action_new_quotation()['context']
        quotation = self.env['sale.order'].with_context(quotation_context).create({})
        self.assertEqual(quotation.planning_slot_id, self.intervention)
        self.intervention._compute_quotations_count()  # it means we return to the form view of the intervention, So the compute will be trigger again.
        self.assertEqual(self.intervention.quotations_count, 1, '1 quotation should be linked to the intervention since we create a quotation via the Create Quotation button.')
        self.assertEqual(self.intervention.action_view_quotations()['res_id'], quotation.id, "Created quotation id should be in the action")
        # The salesperson is accessing the pricelist_id.
        user_salesperson = new_test_user(self.env, 'salesperson', 'sales_team.group_sale_salesman,planning.group_planning_manager')
        intervention = self.intervention.with_user(user_salesperson)
        self.assertEqual(intervention.pricelist_id, self.intervention.sale_order_id.pricelist_id,
            'The intervention and sale order pricelists should be the same.')
        self.assertEqual(intervention.currency_id, self.intervention.sale_order_id.currency_id,
            'The intervention and sale order currency should be the same.')
