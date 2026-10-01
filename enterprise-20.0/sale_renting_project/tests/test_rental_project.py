from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.sale_project.tests.common import TestSaleProjectCommon


@tagged('post_install', '-at_install')
class TestSaleRentingProject(TestSaleProjectCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.product_service_rental = cls.env['product.product'].create({
            'name': 'Projector Rental',
            'type': 'service',
            'sale_ok': True,
        })

        cls.sale_order_standard, cls.sale_order_rental = cls.env['sale.order'].create([{
            'partner_id': cls.partner.id,
            'project_id': cls.project_global.id,
            'order_line': [Command.create({'product_id': cls.product_delivery_manual1.id, 'product_uom_qty': 1})]
        }, {
            'partner_id': cls.partner.id,
            'project_id': cls.project_global.id,
            'rental_start_date': fields.Datetime.now(),
            'rental_return_date': fields.Datetime.now() + timedelta(days=2),
            'is_rental_order': True,
            'order_line': [Command.create({'product_id': cls.product_service_rental.id, 'product_uom_qty': 1})]
        }])

    def test_action_view_sos_stat_button_domain(self):
        """Ensure the project sales stat button domain retrieves both standard and rental orders."""
        action = self.project_global.action_view_sos()
        sale_orders = self.env['sale.order'].search(action.get('domain', []))
        self.assertIn(self.sale_order_standard, sale_orders, "The standard sale order should be included.")
        self.assertIn(self.sale_order_rental, sale_orders, "The rental sale order should be included.")

    def test_action_view_sos_embedded_actions_domain(self):
        """Ensure the embedded actions only retrieve the relevant sale orders."""
        sales_action = self.project_global.with_context(from_embedded_action=True).action_view_sos()
        sales_orders = self.env['sale.order'].search(sales_action.get('domain', []))
        self.assertIn(self.sale_order_standard, sales_orders, "The standard sale order should be included.")
        self.assertNotIn(self.sale_order_rental, sales_orders, "The rental sale order should be excluded.")

        rental_action = self.project_global.with_context(from_embedded_action=True, is_rental_order=True).action_view_sos()
        rental_orders = self.env['sale.order'].search(rental_action.get('domain', []))
        self.assertIn(self.sale_order_rental, rental_orders, "The rental sale order should be included.")
        self.assertNotIn(self.sale_order_standard, rental_orders, "The standard sale order should be excluded.")
