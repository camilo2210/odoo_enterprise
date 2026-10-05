# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged, Form, new_test_user
from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheet


@tagged("-at_install", "post_install", "helpdesk_sale_timesheet")
class TestSaleTimesheetInTicket(TestCommonSaleTimesheet):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def get_default_groups(cls):
        return super().get_default_groups() + cls.env.ref('helpdesk.group_helpdesk_manager')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.helpdesk_team = cls.env['helpdesk.team'].create({
            'name': 'Test Team',
            'use_helpdesk_timesheet': True,
            'use_helpdesk_sale_timesheet': True,
            'project_id': cls.project_task_rate.id,
        })

    def test_compute_sale_line_id_in_ticket(self):
        """ Test to check if the _compute_sale_line_id method correctly works

            Test Case:
            =========
            1) Create ticket in the team,
            2) Check if the SOL defined in ticket is the one containing the prepaid service product
        """
        # 1) Create ticket in the team
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket',
            'team_id': self.helpdesk_team.id,
            'partner_id': self.partner_b.id,
        })

        # 2) Check if the SOL defined in ticket is the one containing the prepaid service product
        self.assertEqual(ticket.sale_line_id, self.so.order_line[-1], "The SOL in the ticket should be the one containing the prepaid service product.")

    def test_compute_so_line_in_timesheet(self):
        """ Test to check if the SOL computed for the timesheets in the ticket is the expected one.

            Test Case:
            =========
            1) Create ticket in the team,
            2) Check if the SOL defined in the ticket is the one containing the prepaid service product,
            3) Create timesheet and check if the SOL in the timesheet is the one in the SOL,
            4) Change the SOL in the ticket and check if the SOL in the timesheet also changes.
        """
        # 1) Create ticket in the team
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket',
            'team_id': self.helpdesk_team.id,
            'partner_id': self.partner_b.id,
        })

        # 2) Check if the SOL defined in ticket is the one containing the prepaid service product
        self.assertEqual(ticket.sale_line_id, self.so.order_line[-1], "The SOL in the ticket should be the one containing the prepaid service product.")

        # 3) Create timesheet and check if the SOL in the timesheet is the one in the SOL
        timesheet = self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'project_id': self.project_task_rate,
            'helpdesk_ticket_id': ticket.id,
            'unit_amount': 2,
            'employee_id': self.employee_user.id,
        })
        self.assertEqual(timesheet.so_line, ticket.sale_line_id, "The SOL in the timesheet should be the one in the ticket.")

        # 4) Change the SOL in the ticket and check if the SOL in the timesheet also changes.
        ticket.write({
            'sale_line_id': self.so.order_line[0].id
        })
        self.assertEqual(ticket.sale_line_id, self.so.order_line[0], "The SOL in the ticket should be the one chosen.")
        self.assertEqual(timesheet.so_line, ticket.sale_line_id, "The SOL in the timesheet should be the one in the ticket.")

    def test_change_customer_and_SOL_after_invoiced_timesheet(self):
        """ Test to check if the partner computed for an invoiced timesheet in the ticket is the expected one.

            Test Case:
            =========
            1) Create ticket with a partner set,
            2) Create timesheet and check if the partner in the timesheet is the one in the ticket,
            3) Invoice and post the SOL linked to the timesheet,
            4) Create a new timesheet entry in the ticket,
            5) Change the ticket's partner and check if the first timesheet's partner stayed the same but the second one changed.
        """
        helpdesk_ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket',
            'team_id': self.helpdesk_team.id,
            'partner_id': self.partner_b.id,
        })
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_b.id,
            'partner_invoice_id': self.partner_b.id,
            'partner_shipping_id': self.partner_b.id,
        })
        so_line_order_no_task = self.env['sale.order.line'].create({
            'name': self.product_delivery_timesheet1.name,
            'product_id': self.product_delivery_timesheet1.id,
            'product_uom_qty': 1,
            'price_unit': self.product_delivery_timesheet1.list_price,
            'order_id': sale_order.id,
        })

        sale_order.action_confirm()

        timesheet_entry = self.env['account.analytic.line'].create({
            'name': 'the only timesheet. So lonely...',
            'helpdesk_ticket_id': helpdesk_ticket.id,
            'project_id': self.helpdesk_team.project_id.id,
            'unit_amount': 3,
            'employee_id': self.employee_user.id,
        })
        helpdesk_ticket.write({
            'sale_line_id': so_line_order_no_task.id,
        })

        self.assertEqual(timesheet_entry.partner_id, self.partner_b, "The Timesheet entry's partner should be equal to the ticket's partner/customer")

        invoice = sale_order._create_invoices()
        invoice.action_post()

        timesheet_entry_2 = self.env['account.analytic.line'].create({
            'name': 'A brother for the lonely timesheet',
            'helpdesk_ticket_id': helpdesk_ticket.id,
            'project_id': self.helpdesk_team.project_id.id,
            'unit_amount': 2,
            'employee_id': self.employee_user.id,
        })

        helpdesk_ticket.write({'partner_id': self.partner_a.id})

        self.assertEqual(timesheet_entry.partner_id, self.partner_b, "The invoiced and posted Timesheet entry should have its partner unchanged")
        self.assertEqual(timesheet_entry_2.partner_id, self.partner_a, "The second Timesheet entry should have its partner changed, as it was not invoiced and posted")

    def test_add_timesheet_line_and_get_remaining_so_hours(self):
        """Test that ticket remaining time is correctly computed, using the timesheet "uom" rather than the "sol" one.
        Test Case:
        =========
        - Create a custom Unit of Measure (eg.: 50hours)
        - Create a service product
        - Create a sale order on that product
        - Get the ticket associated
        - Add a line in the timesheet lines (3 hours worked)
        - Ensure we got the good remaining time when we change from the view form (47 hours)
        """

        # We create a unit of measure of 50 hours
        uom = self.env["uom.uom"].create({
            "name": "50(hours)",
            "relative_factor": 6.25,
            "relative_uom_id": self.env.ref("uom.product_uom_day").id,
        })

        service = self.env["product.product"].create({
            "name": "testService",
            "type": "service",
            "service_policy": "ordered_prepaid",
            "list_price": 1000.,
            "service_tracking": "task_in_project",
            "uom_id": uom.id,
        })

        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner_a.id,
            'partner_invoice_id': self.partner_a.id,
            'partner_shipping_id': self.partner_a.id,
        })

        self.env["sale.order.line"].create({
            'name': service.name,
            'product_id': service.id,
            'product_uom_qty': 1,
            'price_unit': service.list_price,
            'order_id': sale_order.id,
            'tax_ids': False,
        })

        sale_order.action_confirm()

        ticket = self.env["helpdesk.ticket"].create({
            "name": "test_ticket",
            "sale_order_id": sale_order.id,
            "partner_id": self.partner_a.id,
            "team_id": self.helpdesk_team.id,
        })

        # We edit the form of the helpdesk ticket and after add a 3 hours timesheet line
        # we must have a remaining hours of 47
        with Form(ticket) as f:
            with f.timesheet_ids.new() as line:
                line.employee_id = self.employee_user
                line.name = "/",
                line.unit_amount = 3
            self.assertEqual(f.remaining_hours_so, 47)

    def test_sale_order_helpdesk_team_in_context(self):
        """
            Check that we have the helpdesk team id in the context
            when we want to see the tickets linked to a sale order.
        """
        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner_a.id,
            'partner_invoice_id': self.partner_a.id,
            'partner_shipping_id': self.partner_a.id,
        })
        ticket = self.env["helpdesk.ticket"].create({
            "name": "test_ticket",
            "sale_order_id": sale_order.id,
            "partner_id": self.partner_a.id,
            "team_id": self.helpdesk_team.id,
        })
        action = sale_order.action_view_tickets()
        self.assertEqual(action['context']['default_team_id'], ticket.team_id.id)

    def test_compute_commercial_partner_id(self):
        """
            The purpose is to test if the timesheet commecial partner is
            the commercial partner of the partner linked to the helkpdesk ticket.
        """
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket',
            'team_id': self.helpdesk_team.id,
            'partner_id': self.partner_a.id,
        })
        timesheet = self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'project_id': self.helpdesk_team.project_id.id,
            'helpdesk_ticket_id': ticket.id,
            'employee_id': self.employee_user.id,
        })
        self.assertEqual(timesheet.commercial_partner_id, ticket.commercial_partner_id)

    def test_compute_display_sol(self):
        project = self.env['project.project'].create({
            'name': 'Test Project',
            'privacy_visibility': 'followers',
        })
        timesheet = self.env['account.analytic.line'].create({
            'name': 'Test Timesheet',
            'project_id': project.id,
            'employee_id': self.employee_user.id,
        })
        timesheet_manager_no_project_user = new_test_user(
            self.env,
            login='no_project_user',
            groups='hr_timesheet.group_timesheet_manager'
        )
        self.assertFalse(
            timesheet.with_user(timesheet_manager_no_project_user).display_sol,
            "display_sol should be False"
        )

    def test_allowing_service_product_type_sol_in_helpdesk(self):
        """ Test to validate allowing service product type in ticket """

        # Create a sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
        })

        # Create a sale order line with a consumable product
        sale_order_line = self.env['sale.order.line'].create({
            'order_id': sale_order.id,  # Corrected reference to the created sale order
            'product_id': self.product_consumable.id,
            'product_uom_qty': 10,
        })

        # Confirm the sale order
        sale_order.action_confirm()

        # Test that creating a helpdesk ticket with a non-service product raises a ValidationError
        with self.assertRaises(ValidationError, msg="Creating a helpdesk ticket with a non-service product should raise a ValidationError"):
            self.env['helpdesk.ticket'].create({
                'name': 'Test Ticket with non_service Product',
                'team_id': self.helpdesk_team.id,
                'partner_id': self.partner_a.id,
                'sale_line_id': sale_order_line.id,
            })

    def test_confirm_so_on_ticket_creation(self):
        so1, so2 = self.env['sale.order'].create([{
            'name': 'Sale Order 1',
            'partner_id': self.partner_a.id,
        }, {
            'name': 'Sale Order 2',
            'partner_id': self.partner_a.id,
        }])
        sol1, sol2 = self.env['sale.order.line'].create([{
            'order_id': so1.id,
            'product_id': self.product_delivery_timesheet1.id,
        }, {
            'order_id': so2.id,
            'product_id': self.product_delivery_timesheet1.id,
        }])
        self.assertEqual(so1.state, 'draft')
        self.assertEqual(so2.state, 'draft')

        self.env['helpdesk.ticket'].create([{
            'name': 'Test Ticket 1',
            'team_id': self.helpdesk_team.id,
            'sale_line_id': sol1.id,
        }, {
            'name': 'Test Ticket 2',
            'team_id': self.helpdesk_team.id,
            'sale_line_id': sol2.id,
        }])
        self.assertEqual(so1.state, 'sale')
        self.assertEqual(so2.state, 'sale')

    def test_merge_respects_destination_sale_line(self):
        if not self.env["ir.module.module"].search([("name", "=", "data_merge_helpdesk"), ("state", "=", "installed")]):
            self.skipTest("The data_merge_helpdesk module is needed to test merging helpdesk ticket with timesheets")

        so_a = self.env["sale.order"].create({
            "partner_id": self.partner_a.id,
            "order_line": [
                (0, 0, {"product_id": self.product_delivery_timesheet1.id})
            ],
        })
        so_b = self.env["sale.order"].create({
            "partner_id": self.partner_a.id,
            "order_line": [
                (0, 0, {'product_id': self.product_delivery_timesheet1.id})
            ],
        })

        sol_a = so_a.order_line[0]
        sol_b = so_b.order_line[0]

        source_ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket 1',
            'team_id': self.helpdesk_team.id,
            'sale_line_id': sol_a.id,
        })
        dest_ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Ticket 2',
            'team_id': self.helpdesk_team.id,
            'sale_line_id': sol_b.id,
        })

        timesheet_src = self.env["account.analytic.line"].create({
            "employee_id": self.employee_user.id,
            "so_line": sol_a.id,
            "unit_amount": 1,
            "helpdesk_ticket_id": source_ticket.id
        })

        self.env['helpdesk.ticket']._merge_method(dest_ticket, source_ticket)

        # the destination should have properties linking to sale order B
        self.assertEqual(timesheet_src.so_line.id, sol_b.id)
        self.assertEqual(timesheet_src.order_id.id, so_b.id)

    def test_create_invoice_action(self):
        """Test invoice creation from helpdesk tickets.

        Test cases:
            Case 1:
                - Create a ticket without a sale order line.
                - Try to create an invoice.
                - Verify the error message.

            Case 2:
                - Create a ticket linked to a sale order line.
                - Create an invoice from the sale order.
                - Try to create another invoice from the helpdesk ticket.
                - Verify the error message.

            Case 3:
                - Create two tickets, one linked to an already invoiced sale order
                line and the other without a sale order line.
                - Try to create an invoice for both tickets.
                - Verify the error message.

            Case 4:
                - Create a helpdesk ticket.
                - Create a sale order and link its sale order line to the ticket.
                - Create and post the invoice.
                - Verify the helpdesk ticket's invoice count.
        """
        # Test case 1:
        ticket_a, ticket_b = self.env["helpdesk.ticket"].create([
            {
                "name": "Test Ticket A",
                "team_id": self.helpdesk_team.id,
                "partner_id": self.partner_b.id,
                "sale_line_id": False,
            }, {
                "name": "Test Ticket B",
                "team_id": self.helpdesk_team.id,
                "partner_id": self.partner_b.id,
                "sale_line_id": False,
            },
        ])

        action = ticket_a.action_create_invoice()
        self.assertEqual(
            action["params"]["message"],
            "No invoice was created because none of the selected tickets are billable.",
        )

        # Test case 2
        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner_a.id,
            "order_line": [
                Command.create({
                    "product_id": self.product_order_timesheet1.id,
                }),
            ],
        })
        sale_order.action_confirm()
        sale_order._create_invoices()

        ticket_a.sale_line_id = sale_order.order_line.id

        action = ticket_a.action_create_invoice()
        self.assertEqual(
            action["params"]["message"],
            "No invoice was created because none of the selected tickets "
            "have sale orders ready to be invoiced.",
        )

        # Test case 3
        sale_order.invoice_ids.unlink()

        action = (ticket_a + ticket_b).action_create_invoice()
        self.assertEqual(
            action["params"]["message"],
            "No invoice was created because some of the selected tickets "
            "are not billable.",
        )

        # Test case 4
        action = ticket_a.action_create_invoice()
        self.assertEqual(
            action["xml_id"],
            "sale.action_view_sale_advance_payment_inv",
        )
        self.assertEqual(ticket_a.invoice_count, 0)

        payment_wizard = self.env["sale.advance.payment.inv"].with_context(action["context"]).create({})
        action = payment_wizard.create_invoices()
        invoice = self.env["account.move"].browse(action["res_id"])
        invoice.action_post()
        self.assertEqual(ticket_a.invoice_count, 1)
