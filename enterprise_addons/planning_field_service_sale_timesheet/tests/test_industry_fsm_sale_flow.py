# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import Command
from .common import TestPlanningFieldServiceSaleTimesheetCommon
from odoo.tests import Form, freeze_time, new_test_user
from odoo.tools.float_utils import float_compare


@freeze_time("2026-02-27 08:00:00")
class TestFsmFlowSale(TestPlanningFieldServiceSaleTimesheetCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intervention.write({
            'resource_ids': cls.george_employee.resource_id.ids,
            'state': '3_in_progress',
            'partner_id': cls.partner_1.id,
        })
        if 'project_id' in cls.intervention._fields:
            cls.intervention.project_id = cls.field_service_project
        else:
            cls.env['res.config.settings'].create({'planning_project_id': cls.field_service_project.id}).execute()

    def test_invoicing_flow(self):
        self.skipTest("YTI TODO: Broken test to reintroduce.")
        self.service_product_ordered.write({
            'type': 'service',
            'service_policy': 'ordered_prepaid',
        })
        self.service_product_delivered.write({
            'type': 'service',
            'service_policy': 'delivered_timesheet',
        })

        self.george_employee.write({
            'timesheet_product_id': self.service_product_delivered.id,
        })

        self.assertFalse(self.intervention.sale_order_id)
        self.assertFalse(self.intervention.sale_line_id)
        self.service_product_ordered.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).set_fsm_quantity(1.0)
        self.assertEqual(len(self.intervention.sale_order_id.order_line), 1)

        first_order_line = self.intervention.sale_order_id.order_line
        self.assertEqual(first_order_line.product_uom_qty, 1.0)
        self.assertFalse(self.intervention.sale_line_id)

        self.assertFalse(self.intervention.intervention_timesheet_ids)
        if self.env['ir.module.module'].search([('name', '=', 'planning_field_service_sale_stock')]).state != 'installed':
            self.assertNotEqual(self.intervention.sale_order_id.state, 'sale')
        with freeze_time(self.intervention.start_datetime + relativedelta(hours=4)):
            self.intervention.action_complete()
        self.assertEqual(len(self.intervention.intervention_timesheet_ids), 1)
        self.assertEqual(self.intervention.sale_order_id.state, 'sale')
        self.assertEqual(len(self.intervention.sale_order_id.order_line), 2)
        self.assertEqual(len(self.intervention.intervention_timesheet_ids.so_line), 1)
        self.assertEqual(self.intervention.sale_order_id.order_line.mapped('qty_delivered'), [1.0, 4.0])
        self.assertEqual(self.intervention.sale_line_id.product_id, self.service_product_delivered)
        second_order_line = self.intervention.sale_line_id
        self.assertEqual(second_order_line.project_id, self.field_service_project)
        self.assertEqual(second_order_line.planning_slot_id, self.intervention)
        self.assertTrue(second_order_line.is_service)
        self.assertEqual(second_order_line.qty_delivered_method, 'timesheet')

        self.service_product_ordered.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        moves = self.intervention.sale_order_id._create_invoices()
        self.assertEqual(len(moves), 1, "One invoice should be generated with success")

    def test_bill_planning_field_service_with_diff_shipping_address(self):
        """
        When the shipping address is different from the invoice address,
        the intervention should be able to be invoiced once done.
        """
        # activate setting for splitting the invoice and shipping address
        config = self.env['res.config.settings'].create({
            'group_sale_delivery_address': True,
        })
        config.execute()
        field_service_product = self.env['product.product'].create({
            'name': 'Field Service Product',
            'type': 'service',
            'list_price': 100,
            'planning_enabled': True,
        })
        billing_partner, shipping_partner = self.env['res.partner'].create([{
            'name': 'Billing Partner',
        }, {
            'name': 'Shipping Partner',
        }])
        sale_order = self.env['sale.order'].create({
            'partner_id': billing_partner.id,
            'partner_invoice_id': billing_partner.id,
            'partner_shipping_id': shipping_partner.id,
        })
        sale_order.order_line = self.env['sale.order.line'].create([{
            'product_id': field_service_product.id,
            'product_uom_qty': 1.0,
            'order_id': sale_order.id,
        }])
        sale_order.action_confirm()
        self.assertEqual(len(sale_order.order_line.planning_slot_ids), 1, "We should have 1 intervention after confirming the SO.")
        intervention = sale_order.order_line.planning_slot_ids[0]
        self.assertEqual(intervention.partner_id.commercial_partner_id, shipping_partner,
                         "Partner on the intervention should be the shipping address.")
        self.assertEqual(intervention.sale_order_id, sale_order, "The sale order should be linked to the intervention.")
        intervention.action_complete()

    def test_intervention_sale_order_id_and_sale_order_line_id_consistency(self):
        sale_order_1 = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
            'order_line': [
                Command.create({
                    'product_id': self.product_delivery_timesheet1.id,
                    'product_uom_qty': 10,
                })
            ]
        })
        sale_order_1.action_confirm()

        intervention = self.env['planning.slot'].create({
            'sale_line_id': sale_order_1.order_line.id,
            'name': 'Test Intervention',
            'start_datetime': datetime.now(),
            'end_datetime': datetime.now() + relativedelta(hours=2),
            'state': '3_in_progress',
        })

        self.assertEqual(intervention.sale_order_id.id, sale_order_1.id)

        sale_order_2 = sale_order_1.copy()

        intervention.write({
            'sale_line_id': sale_order_2.order_line.id,
        })

        self.assertEqual(intervention.sale_order_id.id, sale_order_2.id)

    def test_qty_to_invoice_from_fsm(self):
        """
        Check that sale order lines coming from an intervention and for a product with a price of zero
        are not going to be invoiced.
        """
        product = self.product_a.with_context({'intervention_id': self.intervention.id})
        product.set_fsm_quantity(2)
        so = self.intervention.sale_order_id
        if so.state == 'draft':
            so.action_confirm()  # needed if stock is not installed
        sol = so.order_line[-1]
        self.assertEqual(sol.qty_to_invoice, 2.0)

        so_form = Form(so)
        with so_form.order_line.edit(0) as line:
            line.price_unit = 0.0
        so_form.save()
        self.assertEqual(sol.qty_to_invoice, 2.0, "Anglo Saxon Accounting should be enable")

        with so_form.order_line.edit(0) as line:
            line.price_unit = 0.01
        so_form.save()
        self.assertEqual(sol.qty_to_invoice, 2.0, "$0.01 shouldn't count as free")
        self.env.company.anglo_saxon_accounting = False
        with so_form.order_line.edit(0) as line:
            line.price_unit = 0.00
        so_form.save()
        self.assertEqual(sol.qty_to_invoice, 0.0, "Anglo Saxon Accounting should be disable")

    @freeze_time("2026-02-27 08:00:00")
    def test_uom_conversion_intervention_to_so(self):
        """Checks that the hours recorded on Timesheets are converted to the correct UOM on the Sales Order"""

        quarter_hour = self.env['uom.uom'].create({
            'name': 'Quarter-Hours',
            'relative_factor': 0.25,
            'relative_uom_id': self.env.ref('uom.product_uom_hour').id,
        })
        self.service_timesheet._inverse_service_policy()  # trigger value changes for invoice policy and service_type
        self.service_timesheet.uom_id = quarter_hour
        self.service_timesheet.list_price = 40
        self.employee_user2.timesheet_product_id = self.service_timesheet
        intervention = self.env['planning.slot'].create({
            'name': 'Field Service',
            'resource_ids': self.employee_user2.resource_id.ids,
            'partner_id': self.partner_1.id,
            'allocated_hours': 1.75,
            'state': '3_in_progress',
        })
        self.set_field_service_project(self.field_service_project, intervention)
        with freeze_time(intervention.start_datetime + relativedelta(hours=1.75)):
            intervention.action_complete()
        sale_order = intervention.sale_order_id
        order_lines = sale_order.order_line
        self.assertEqual(float_compare(order_lines.product_uom_qty, 7.0, precision_digits=2), 0, "The Ordered Quantities should match the Timesheets at the time of creation")

    def test_prevent_empty_sol_for_timesheet(self):
        """
        Test that when adding a product to the intervention and mark as done that intervention then,
        it does not create an empty SOL for timesheet if no timesheets are added.

        Test Case:
        =========
        1. Create a intervention and add a product to it
        2. Validate the intervention
        3. Check the sale order line should not be created for timesheet
        """
        self.field_service_project.write({
            'timesheet_product_id': self.service_timesheet.id,
        })
        self.service_product_ordered.with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.intervention.action_complete()
        sale_order_lines = self.env['sale.order.line'].search([('order_id', '=', self.intervention.sale_order_id.id)])
        self.assertEqual(len(sale_order_lines), 2)
        self.assertIn(self.service_product_ordered, sale_order_lines.product_id)

    def test_task_sale_order_auto_fills_salesperson(self):
        """
        Check that sale order has an assigned salesperson by default when adding products to it.
        Expected behavior is: 1st assignee if any, current user if not
        """
        assignee_1 = new_test_user(self.env, login='john', groups='sales_team.group_sale_salesman,account.group_account_invoice')
        assignee_2 = new_test_user(self.env, login='albert')
        employee_1, employee_2 = self.env['hr.employee'].create([
            {'name': 'employee 1', 'user_id': assignee_1.id},
            {'name': 'employee 2', 'user_id': assignee_2.id},
        ])

        intervention_no_assignee, intervention_with_assignee = self.env['planning.slot'].with_context({
            'default_state': '3_in_progress',
        }).create([
            {
                'name': 'No assignee',
                'partner_id': self.partner_1.id
            },
            {
                'name': 'With assignee',
                'partner_id': self.partner_1.id,
                'resource_ids': [employee_1.resource_id.id, employee_2.resource_id.id],
            },
        ])

        # NOTE: use with_user(self.planning_manager) because self.env.user has Sales and Accounting access.
        intervention_without_access = self.env['planning.slot'].with_user(self.planning_manager).create([
            {
                'name': 'Without access',
                'partner_id': self.partner_1.id,
                'resource_ids': [employee_2.resource_id.id],
            },
        ])

        intervention_no_assignee._generate_sale_order()
        intervention_with_assignee._generate_sale_order()
        intervention_without_access._generate_sale_order()
        self.assertEqual(intervention_no_assignee.sale_order_id.user_id, self.env.user)
        self.assertEqual(intervention_with_assignee.sale_order_id.user_id, assignee_1)
        self.assertFalse(intervention_without_access.sale_order_id.user_id)

    def test_invoice_status_after_change_price_for_fully_invoiced_order(self):
        so = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
            'order_line': [
                Command.create({
                    'product_id': self.consu_product_ordered.id,
                    'product_uom_qty': 10,
                })
            ]
        })

        sol = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': self.service_product_delivered.id,
            'product_uom_qty': 3,
            'price_unit': 40,
            'sequence': 20,
            'planning_slot_id': self.intervention.id
        })
        so.action_confirm()
        sol.qty_delivered = 3

        invoice = so._create_invoices()
        invoice.action_post()

        self.assertEqual(so.invoice_status, 'invoiced')
        sol.price_unit = 0
        self.assertEqual(so.invoice_status, 'invoiced')

    def test_invoice_status_so_non_anglo_saxon_intervention_anglo_saxon(self):
        """
        When the SO's company has Anglo-Saxon accounting disabled and the
        material price is zero, the invoice status must be 'invoiced'.
        The intervention's company Anglo-Saxon setting must have no influence.
        """
        self.env['res.config.settings'].create({'group_field_service_allow_material': True}).execute()
        self.env.company.anglo_saxon_accounting = False
        self.company_data_2['company'].anglo_saxon_accounting = True
        fsm_project_second = self.env['project.project'].create({
            'name': 'Field Service second',
            'company_id': self.company_data_2['company'].id,
        })
        second_intervention = self.env['planning.slot'].create({
            'name': 'Second intervention',
            'partner_id': self.partner_1.id,
            'company_id': self.company_data_2['company'].id,
            'state': '3_in_progress',
        })
        self.set_field_service_project(fsm_project_second, second_intervention)
        self.assertTrue(second_intervention.company_id.anglo_saxon_accounting)
        second_intervention_so = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
            'project_id': fsm_project_second.id,
            'company_id': self.env.company.id,
        })
        second_intervention.sale_order_id = second_intervention_so
        self.assertFalse(second_intervention_so.company_id.anglo_saxon_accounting)

        product = self.env['product.product'].create({
            'name': 'product',
            'list_price': 0.0,
            'type': 'consu',
            'invoice_policy': 'order',
        })
        product.with_context({'intervention_id': second_intervention.id}).fsm_add_quantity()

        if second_intervention_so.state == 'draft':
            second_intervention_so.action_confirm()  # needed if stock is not installed
        self.assertRecordValues(second_intervention_so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'no', 'planning_slot_id': second_intervention.id},
        ])
        self.assertEqual(second_intervention_so.invoice_status, 'invoiced')

    def test_invoice_status_so_anglo_saxon_intervention_non_anglo_saxon(self):
        """
        When the SO's company has Anglo-Saxon accounting enabled and the
        material price is zero, the invoice status must be 'to invoice'.
        The intervention's company Anglo-Saxon setting must have no influence.
        """
        self.env['res.config.settings'].create({'group_field_service_allow_material': True}).execute()
        self.env.company.anglo_saxon_accounting = True
        self.company_data_2['company'].anglo_saxon_accounting = False
        fsm_project_second = self.env['project.project'].create({
            'name': 'Field Service second',
            'company_id': self.company_data_2['company'].id,
        })
        second_intervention = self.env['planning.slot'].create({
            'name': 'Second intervention',
            'partner_id': self.partner_1.id,
            'company_id': self.company_data_2['company'].id,
            'state': '3_in_progress',
        })
        self.set_field_service_project(fsm_project_second, second_intervention)
        self.assertFalse(second_intervention.company_id.anglo_saxon_accounting)
        second_intervention_so = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
            'project_id': fsm_project_second.id,
            'company_id': self.env.company.id,
        })
        second_intervention.sale_order_id = second_intervention_so
        self.assertTrue(second_intervention_so.company_id.anglo_saxon_accounting)

        product = self.env['product.product'].create({
            'name': 'product',
            'list_price': 0.0,
            'type': 'consu',
            'invoice_policy': 'order',
        })
        product.with_context({'intervention_id': second_intervention.id}).fsm_add_quantity()

        if second_intervention_so.state == 'draft':
            second_intervention_so.action_confirm()  # needed if stock is not installed
        self.assertRecordValues(second_intervention_so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'to invoice', 'planning_slot_id': second_intervention.id},
        ])
        self.assertEqual(second_intervention_so.invoice_status, 'to invoice')

    def test_invoice_status_with_anglo_saxon(self):
        """
        Verify SO and order line invoice statuses across multiple scenarios
        when Anglo-Saxon accounting is enabled on the SO's company.
        Material lines at price 0 added via FSM must be invoiced like any other line.
        """
        self.env['res.config.settings'].create({'group_field_service_allow_material': True}).execute()
        self.intervention.partner_id = self.partner_1.id
        self.env.company.anglo_saxon_accounting = True
        preexisting_product = self.env['product.product'].create({
            'name': 'pre existing',
            'list_price': 0.0,
            'type': 'consu',
            'invoice_policy': 'order',
        })

        # Case 0: Pre-added product with price is 0 in SO are always to invoice
        so = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
            'order_line': [
                Command.create({
                    'product_id': preexisting_product.id,
                    'price_unit': 0.0,
                }),
            ],
        })
        # Link the intervention here to ensure the pre-added products aren't considered as added materials
        self.intervention.sale_order_id = so
        so.action_confirm()
        self.assertEqual(
            so.invoice_status,
            'to invoice',
            "SO invoice status should be 'to invoice' when anglo-saxon accounting is enabled and lines are not invoiced."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'to invoice', 'planning_slot_id': False},
        ])

        # Case 1: Adding a material at price 0 keeps the SO 'to invoice'; the line is 'to invoice'
        self.env.company.anglo_saxon_accounting = True
        self.consu_product_ordered.list_price = 0.0
        self.consu_product_ordered.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(
            so.invoice_status,
            'to invoice',
            "SO invoice status should be 'to invoice' when anglo-saxon accounting is enabled and lines are not invoiced."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'to invoice', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'to invoice', 'planning_slot_id': self.intervention.id},
        ])
        so._create_invoices()
        self.assertEqual(
            so.invoice_status,
            'invoiced',
            "SO invoice status should be 'invoiced' after invoicing the anglo-saxon line."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': self.intervention.id},
        ])

        # Case 2: Adding a priced line brings the SO back to 'to invoice'; the line is 'to invoice'
        self.service_product_ordered.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(
            so.invoice_status,
            'to invoice',
            "SO invoice status should be 'to invoice' when there is still a line to invoice."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': self.intervention.id},
            {'price_unit': 885.0, 'invoice_status': 'to invoice', 'planning_slot_id': self.intervention.id},
        ])

        # Case 3: After invoicing all lines, the SO is 'invoiced'
        so._create_invoices()
        self.assertEqual(
            so.invoice_status,
            'invoiced',
            "SO invoice status should be 'invoiced' after all lines are invoiced."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': self.intervention.id},
            {'price_unit': 885.0, 'invoice_status': 'invoiced', 'planning_slot_id': self.intervention.id},
        ])

    def test_invoice_status_without_anglo_saxon(self):
        """
        Verify SO and order line invoice statuses across multiple scenarios
        when Anglo-Saxon accounting is disabled on the SO's company.
        Material lines at price 0 added via FSM are ignored ('no') and must
        not prevent the SO from reaching 'invoiced'.
        """
        self.env['res.config.settings'].create({'group_field_service_allow_material': True}).execute()
        self.intervention.partner_id = self.partner_1.id
        self.env.company.anglo_saxon_accounting = False
        preexisting_product = self.env['product.product'].create({
            'name': 'pre existing',
            'list_price': 0.0,
            'type': 'consu',
            'invoice_policy': 'order',
        })

        # Case 0: A pre-existing line at price 0 is always 'to invoice'
        so = self.env['sale.order'].create({
            'partner_id': self.partner_1.id,
            'order_line': [
                Command.create({
                    'product_id': preexisting_product.id,
                    'price_unit': 0.0,
                }),
            ],
        })
        # Link the intervention here to ensure the pre-added products aren't considered as added materials
        self.intervention.sale_order_id = so
        so.action_confirm()
        self.assertEqual(
            so.invoice_status,
            'to invoice',
            "SO invoice status should be 'to invoice' when anglo-saxon accounting is enabled and lines are not invoiced."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'to invoice', 'planning_slot_id': False},
        ])
        so._create_invoices()

        # Case 1: Adding a material at price 0 keeps the SO 'invoiced'; the line is 'no'
        self.service_product_delivered.list_price = 0.0
        self.service_product_delivered.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(
            so.invoice_status,
            'invoiced',
            "SO invoice status should be 'invoiced' when all remaining lines are material lines with price 0 (non-anglo-saxon)."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'no', 'planning_slot_id': self.intervention.id},
        ])

        # Case 2: Adding a priced line brings the SO back to 'to invoice'; the line is 'to invoice'
        self.service_product_ordered.with_user(self.george_user).with_context({'intervention_id': self.intervention.id}).fsm_add_quantity()
        self.assertEqual(
            so.invoice_status,
            'to invoice',
            "SO invoice status should be 'to invoice' when there is still a line to invoice."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'no', 'planning_slot_id': self.intervention.id},
            {'price_unit': 885.0, 'invoice_status': 'to invoice', 'planning_slot_id': self.intervention.id},
        ])

        # Case 3: After invoicing all lines, the SO is 'invoiced' despite the 'no' line
        so._create_invoices()
        self.assertEqual(
            so.invoice_status,
            'invoiced',
            "SO invoice status should be 'invoiced' after all lines are invoiced."
        )
        self.assertRecordValues(so.order_line, [
            {'price_unit': 0.0, 'invoice_status': 'invoiced', 'planning_slot_id': False},
            {'price_unit': 0.0, 'invoice_status': 'no', 'planning_slot_id': self.intervention.id},
            {'price_unit': 885.0, 'invoice_status': 'invoiced', 'planning_slot_id': self.intervention.id},
        ])
