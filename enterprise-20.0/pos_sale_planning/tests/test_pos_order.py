# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import CommonPosTest


@tagged('post_install', '-at_install')
class TestPosSalePlanningOrder(CommonPosTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.planning_resource = cls.env['resource.resource'].sudo().create({
            'name': 'Room A',
            'resource_type': 'material',
        })
        cls.slot_partner = cls.env['res.partner'].create({'name': 'Slot Customer'})
        cls.service_product = cls.env['product.product'].create({
            'name': 'Room Rental',
            'type': 'service',
            'sale_ok': True,
            'planning_enabled': True,
            'taxes_id': [],
        })

        cls.sale_order = cls.env['sale.order'].sudo().create({
            'partner_id': cls.slot_partner.id,
            'order_line': [Command.create({
                'product_id': cls.service_product.id,
                'product_uom_qty': 1,
            })],
        })
        cls.sale_order.action_confirm()

        now = datetime.now()
        cls.slot = cls.env['planning.slot'].sudo().create({
            'resource_ids': [Command.link(cls.planning_resource.id)],
            'start_datetime': now - timedelta(hours=1),
            'end_datetime': now + timedelta(hours=2),
            'sale_line_id': cls.sale_order.order_line[0].id,
        })
        cls.slot.write({'state': '2_published'})

        cls.resource_pm = cls.env['pos.payment.method'].create({
            'name': 'Resource Payment',
            'type': 'resource',
            'resource_ids': [Command.set([cls.planning_resource.id])],
        })
        cls.pos_config_usd.write({
            'payment_method_ids': [Command.link(cls.resource_pm.id)],
        })

    def _make_pos_order(self, amount=50.0, with_slot=True):
        self.pos_config_usd.open_ui()
        session = self.pos_config_usd.current_session_id
        order = self.env['pos.order'].create({
            'session_id': session.id,
            'partner_id': self.slot_partner.id,
            'planning_slot_id': self.slot.id if with_slot else False,
            'amount_total': amount,
            'amount_paid': 0.0,
            'amount_tax': 0.0,
            'amount_return': 0.0,
            'lines': [Command.create({
                'product_id': self.service_product.id,
                'qty': 1,
                'price_unit': amount,
                'price_subtotal': amount,
                'price_subtotal_incl': amount,
                'tax_ids': [],
            })],
        })
        payment_method = self.resource_pm if with_slot else self.cash_payment_method
        self.env['pos.payment'].create({
            'pos_order_id': order.id,
            'payment_method_id': payment_method.id,
            'amount': amount,
        })
        order.amount_paid = amount
        return order

    def test_payment_creates_section_line_on_sale_order(self):
        """action_pos_order_paid creates exactly one section line on the linked SO."""
        initial_count = len(self.sale_order.order_line)
        order = self._make_pos_order()
        order.action_pos_order_paid()

        new_lines = self.sale_order.order_line[initial_count:]
        self.assertEqual(len(new_lines), 2, "Two new lines should be created: one section line and one product line.")
        section = new_lines[0]
        self.assertEqual(section.display_type, 'line_section')
        self.assertIn(order.name, section.name)
        self.assertIn(self.pos_config_usd.name, section.name)
        self.assertIn(self.planning_resource.display_name, section.name)

    def test_no_so_lines_for_order_without_planning_slot(self):
        """Orders not linked to a planning slot create no SO lines."""
        initial_count = len(self.sale_order.order_line)
        order = self._make_pos_order(with_slot=False)
        order.action_pos_order_paid()

        self.assertEqual(
            len(self.sale_order.order_line),
            initial_count,
            "No SO lines should be created when the order has no planning slot."
        )
