# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import Command, fields
from .common import TestPlanningFieldServiceSaleTimesheetCommon


class TestPlanningSlot(TestPlanningFieldServiceSaleTimesheetCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_partner_id_follows_so_shipping_address(self):
        """ For intervention linked to a sale order, the partner_id should be the same as
            the partner_shipping_id set on the sale sale order.
        """
        self.env.user.group_ids += self.env.ref('account.group_delivery_invoice_address')
        so = self.env['sale.order'].create([{
            'name': 'Test SO linked to intervention',
            'partner_id': self.partner_1.id,
        }])
        sol = self.env['sale.order.line'].create([{
            'name': 'Test SOL linked to a intervention',
            'order_id': so.id,
            'planning_slot_id': self.intervention.id,
            'product_id': self.service_product_delivered.id,
            'product_uom_qty': 3,
        }])
        self.intervention.sale_line_id = sol
        partner_2 = self.env['res.partner'].create({'name': 'A Test Partner 2'})

        # 1. Modifying shipping address on SO should update the customer on the intervention
        self.assertEqual(so.partner_id, self.partner_1)
        self.assertEqual(so.partner_shipping_id, self.partner_1)
        self.assertEqual(self.intervention.partner_id, self.partner_1)

        so.partner_shipping_id = partner_2

        self.assertEqual(so.partner_id, self.partner_1)
        self.assertEqual(so.partner_shipping_id, partner_2)
        self.assertEqual(self.intervention.partner_id, partner_2,
                         "Modifying the shipping partner on a sale order linked to a intervention should update the partner of this intervention accordingly")

    def test_under_warranty(self):
        """ Ensure that the product price is zero in the sales order line for intervention is under warranty.
                Test Case:
                =========
                1. Create a intervention and add timesheet line to it
                2. Set the intervention under warranty
                3. Validate the intervention
                4. Check the price unit of the sale order line
        """
        self.intervention.write({'under_warranty': True, 'partner_id': self.partner_1.id, 'state': '3_in_progress', 'resource_ids': self.current_employee.resource_id.ids})
        self.set_field_service_project(self.field_service_project, self.intervention)
        self.assertFalse(self.intervention.sale_line_id)
        self.assertFalse(self.intervention.intervention_timesheet_ids)
        self.assertFalse(self.intervention.sale_order_id)
        self.intervention.action_complete()
        self.intervention.invalidate_recordset(['intervention_timesheet_ids'])
        self.assertTrue(self.intervention.intervention_timesheet_ids)
        self.assertFalse(self.intervention.sale_line_id)
        self.assertFalse(self.intervention.sale_order_id)

        self.second_intervention.write({'under_warranty': True, 'partner_id': self.partner_1.id, 'state': '3_in_progress', 'resource_ids': self.current_employee.resource_id.ids})
        self.set_field_service_project(self.env['project.project'], self.second_intervention)
        self.consu_product_ordered.with_context(intervention_id=self.second_intervention.id).set_fsm_quantity(2)
        self.second_intervention.action_complete()
        self.assertFalse(self.second_intervention.intervention_timesheet_ids)
        self.assertTrue(self.second_intervention.sale_order_id)
        self.assertFalse(self.second_intervention.sale_line_id)
        self.assertEqual(len(self.second_intervention.sale_order_id.order_line), 1)

    def test_warranty_status_updates_sale_order_line_price(self):
        """
        Ensure that the product price is zero in the sales order line
        when the intervention is under warranty.
            Test Case:
            ==========
            1. Create a sales order linked to the customer.
            2. Assign a customer (partner) to the intervention and link the intervention to the sales order.
            3. Create a sales order line for a product and link it to the intervention.
            4. Verify the price unit matches the product's list price by default.
            5. Set the intervention as under warranty.
            6. Verify the price unit is set to 0.0 in the sales order line.
            7. Unset the warranty status.
            8. Verify the price unit returns to the product's list price.
        """
        so = self.env['sale.order'].create([{
            'name': 'Test SO linked to fsm intervention',
            'partner_id': self.partner_1.id,
        }])
        self.intervention.write({'partner_id': self.partner_1.id, 'sale_order_id': so, 'state': '3_in_progress'})
        sol = self.env['sale.order.line'].create([{
            'name': 'Test SOL linked to a fsm tasl',
            'order_id': so.id,
            'planning_slot_id': self.intervention.id,
            'product_id': self.consu_product_delivered.id,
            'product_uom_qty': 3,
        }])

        self.assertEqual(sol.price_unit, self.consu_product_delivered.list_price, "The price should match the product's listed price.")
        self.intervention.under_warranty = True
        self.assertEqual(sol.price_unit, 0.0, "If intervention is under warranty, the price of the sale order line should be 0.0")
        self.intervention.under_warranty = False
        self.assertEqual(sol.price_unit, self.consu_product_delivered.list_price, "The price should match the product's listed price.")

    def test_fsm_task_timesheet_uses_customer_pricelist(self):
        """Test that the timesheet service line uses the fixed price from the customer's assigned pricelist.

            Steps to reproduce:
            - Create a fixed-price pricelist that applies to all products.
            - Assign the pricelist to the customer.
            - Create a intervention linked to that customer.
            - Add a timesheet entry to the intervention.
            - Mark the intervention as done.
            - Verify that the price of the timesheet service line in the sale order matches the fixed price from the pricelist.
        """
        pricelist = self.env['product.pricelist'].create({
            'name': 'Price List',
            'currency_id': self.env.company.currency_id.id,
            'item_ids': [Command.create({
                'applied_on': '3_global',
                'compute_price': 'fixed',
                'fixed_price': 0.0,
            })],
        })

        self.partner.property_product_pricelist = pricelist
        self.intervention.partner_id = self.partner
        self.env['account.analytic.line'].create({
            'name': '/',
            'employee_id': self.employee_user2.id,
            'planning_slot_id': self.intervention.id,
            'unit_amount': 2.0,
            'date': '2025-06-17',
        })

        self.intervention.action_complete()
        self.assertEqual(
            self.intervention.sale_line_id.price_unit,
            pricelist.item_ids[0].fixed_price,
            "The service price does not match the fixed price defined in the customer's pricelist."
        )

    def test_compute_sale_order_id(self):
        """
        Check whether a task's sale_order_id is set iff its partner_id matches
        the SO's partner_id, partner_invoice_id, or partner_shipping_id fields.
        """
        partners = [
            self.partner,    # partner_id
            self.partner_a,  # partner_invoice_id
            self.partner_b,  # partner_shipping_id
            self.env['res.partner'].create({'name': "unrelated partner"}),
        ]
        sale_order = self.env['sale.order'].create({
            'partner_id': partners[0].id,
            'partner_invoice_id': partners[1].id,
            'partner_shipping_id': partners[2].id,
            'order_line': [Command.create({'product_id': self.product_order_timesheet1.id})],
        })
        sale_order.action_confirm()

        interventions = self.env['planning.slot'].create([{
            'name': f"Intervention {i}",
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
            'sale_line_id': sale_order.order_line.id,
        } for i in range(len(partners))])
        for intervention, partner in zip(interventions, partners):
            intervention.partner_id = partner
        intervention0, intervention1, intervention2, intervention3 = interventions

        self.assertEqual(intervention0.sale_order_id, sale_order, "intervention matches SO's partner_id")
        self.assertEqual(intervention1.sale_order_id, sale_order, "intervention matches SO's partner_invoice_id")
        self.assertEqual(intervention2.sale_order_id, sale_order, "intervention matches SO's partner_shipping_id")
        self.assertFalse(intervention3.sale_order_id, "intervention partner doesn't match any of the SO partners")
        self.assertFalse(intervention3.sale_line_id, "intervention partner doesn't match any of the SO partners")

        intervention3.write({
            'partner_id': self.partner.id,
            'sale_line_id': sale_order.order_line.id,
        })
        self.assertEqual(intervention3.sale_order_id, sale_order, "Task matches SO's partner_id")

        intervention0, intervention1, intervention2, intervention3 = self.env['planning.slot'].create([{
            'name': f"Intervention {i}",
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
            'sale_line_id': sale_order.order_line.id,
            'partner_id': partner.id,
        } for i, partner in enumerate(partners)])

        self.assertEqual(intervention0.sale_order_id, sale_order, "intervention matches SO's partner_id")
        self.assertEqual(intervention1.sale_order_id, sale_order, "intervention matches SO's partner_invoice_id")
        self.assertEqual(intervention2.sale_order_id, sale_order, "intervention matches SO's partner_shipping_id")
        self.assertFalse(intervention3.sale_order_id, "intervention partner doesn't match any of the SO partners")
        self.assertFalse(intervention3.sale_line_id, "intervention partner doesn't match any of the SO partners")

    def test_action_open_timesheets(self):
        """ Check that the Recorded button on an intervention lists the timesheets logged on it. """
        self.set_field_service_project(self.field_service_project, self.intervention)
        intervention_timesheet, _other_timesheet = self.env['account.analytic.line'].create([{
            'name': 'Intervention timesheet',
            'project_id': self.field_service_project.id,
            'planning_slot_id': self.intervention.id,
            'employee_id': self.employee_user2.id,
            'unit_amount': 2.0,
        }, {
            'name': 'Timesheet outside of the intervention',
            'project_id': self.field_service_project.id,
            'employee_id': self.employee_user2.id,
            'unit_amount': 3.0,
        }])

        action = self.intervention.action_open_timesheets()

        self.assertEqual(
            intervention_timesheet,
            self.env['account.analytic.line'].search(action['domain']),
        )
