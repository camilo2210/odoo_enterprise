# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.sale_subscription_stock.tests.common_sale_subscription_stock import TestSubscriptionStockCommon
from odoo.tests import users, tagged


@tagged('post_install', '-at_install')
class TestSaleSubscriptionStockRule(TestSubscriptionStockCommon):

    _test_user_groups = None  # FIXME list needed groups

    def setUp(self):
        super().setUp()
        if 'mrp.production' not in self.env:
            self.skipTest('`mrp` is not installed')

    @users('admin')
    def test_post_invoice_for_mto_product(self):
        prod = self.env['product.product'].create({
            'name': 'Test',
            'is_storable': True,
            'recurring_invoice': True,
        })
        sub = self.env['sale.order'].create({
            'name': 'Order',
            'is_subscription': True,
            'partner_id': self.user_portal.partner_id.id,
            'plan_id': self.plan_month.id,
            'order_line': [
                Command.create({
                    'product_id': prod.id,
                    'product_uom_qty': 1,
                    'tax_ids': [Command.clear()],
                }),
            ]
        })

        sub.action_confirm()
        inv = sub._create_invoices()
        inv.action_post()
        self.assertEqual(inv.move_type, 'out_invoice')
        self.assertEqual(inv.state, 'posted')
