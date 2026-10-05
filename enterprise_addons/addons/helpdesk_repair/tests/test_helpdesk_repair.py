# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, Form
from odoo.addons.helpdesk.tests.common import HelpdeskCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestRepair(HelpdeskCommon):

    def test_helpdesk_repair(self):
        self.test_team.use_product_repairs = True

        product = self.env['product.product'].create({'name': 'Product'})

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': self.partner.id,
            'team_id': self.test_team.id,
        })

        ro_form = Form(self.env['repair.order'].with_context(default_ticket_id=ticket.id))
        ro_form.product_id = product

        repair_order = ro_form.save()
        repair_order._action_repair_confirm()

        self.assertEqual(ticket.repairs_count, 1, 'The ticket should be linked to a return')
        self.assertEqual(repair_order.id, ticket.repair_ids[0].id, 'The correct return should be referenced in the ticket')

        repair_order.action_repair_end()

        last_message = str(ticket.message_ids[0].body)

        self.assertTrue(repair_order.display_name in last_message and 'Repair' in last_message,
            'Repair validation should be logged on the ticket')

    def test_helpdesk_return_and_repair(self):
        """
        Check that the moves linked to a repair are not mimicked on the return.
        """
        self.test_team.use_product_returns = True
        self.test_team.use_product_repairs = True

        self.env['account.account'].create({
            'code': 'X1012',
            'name': 'Debtors - (test)',
            'account_type': 'asset_receivable',
        })
        a_sale = self.env['account.account'].create({
            'code': 'X2020',
            'name': 'Product Sales - (test)',
            'account_type': 'income',
        })
        self.sales_journal = self.env['account.journal'].create({
            'name': 'Sales - Test',
            'code': 'TINV',
            'type': 'sale',
            'default_account_id': a_sale.id,
            'refund_sequence': True,
        })

        product, part = self.env['product.product'].create([
            {
                'name': 'final product',
                'is_storable': True,
            },
            {
                'name': 'part',
                'is_storable': True,
            }
        ])
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        self.env['sale.order.line'].create({
            'product_id': product.id,
            'price_unit': 10,
            'product_uom_qty': 1,
            'order_id': so.id,
        })
        so.action_confirm()
        delivery = so.picking_ids
        delivery.move_ids.quantity = 1
        delivery.move_ids.picked = True
        delivery.button_validate()

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': self.partner.id,
            'team_id': self.test_team.id,
            'sale_order_id': so.id,
        })
        stock_picking_form = Form(self.env['stock.return.picking.helpdesk'].with_context({
            'active_model': 'helpdesk.ticket',
            'default_ticket_id': ticket.id
        }))

        stock_picking_form.picking_id = delivery
        wizzard = stock_picking_form.save()
        return_picking = wizzard.picking_id._create_return()
        return_picking.move_ids.product_uom_qty = 1
        return_picking.action_assign()
        return_picking.button_validate()

        res_dict = ticket.action_repair_order_form()
        ro_form = Form(self.env[(res_dict.get('res_model'))].with_context(res_dict['context']), view=res_dict['view_id'])
        with ro_form.move_ids.new() as move:
            move.product_id = part
            move.product_uom_qty = 1.0
            move.quantity = 1.0
            move.repair_line_type = 'add'
        repair_order = ro_form.save()
        repair_order.action_validate()
        repair_order.action_repair_end()
        delivery = so.picking_ids - return_picking
        self.assertRecordValues(delivery.move_ids, [{'product_id': product.id, 'quantity': 1.0}])
        return_picking = so.picking_ids.filtered(lambda p: p.picking_type_id == so.warehouse_id.in_type_id)
        self.assertRecordValues(return_picking.move_ids, [{'product_id': product.id, 'quantity': 1.0}])

    def test_helpdesk_repair_sale_order_uses_customer_salesperson(self):
        """Ensure quotation created from helpdesk repairs assign the customer's salesperson."""
        self.test_team.use_product_repairs = True
        self.partner.user_id = self.env.user

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test ticket',
            'partner_id': self.partner.id,
            'team_id': self.test_team.id,
        })

        repair_action = ticket.action_repair_order_form()
        repair_order = self.env['repair.order'].with_context(repair_action['context']).create({})

        repair_order.action_create_sale_order()

        self.assertFalse(repair_order.user_id)
        self.assertEqual(repair_order.sale_order_id.user_id, self.env.user)
