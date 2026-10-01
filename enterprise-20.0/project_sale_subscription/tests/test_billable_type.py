from odoo.tests import tagged
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('-at_install', 'post_install')
class TestSubscriptionBillableType(TestSubscriptionCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_analytic_line_billable_type_subscription(self):
        self.subscription.action_confirm()
        line, unlinked_line = self.env['account.analytic.line'].create([{
            'account_id': self.account_1.id,
            'name': 'Subscription revenue',
            'category': 'invoice',
            'so_line': self.subscription.order_line[0].id,
            'product_id': self.product.id,
            'amount': 100,
            'unit_amount': 1,
        }, {
            'account_id': self.account_1.id,
            'name': 'Subscription revenue, not linked to the order',
            'category': 'other',
            'product_id': self.product.id,
            'amount': 100,
            'unit_amount': 1,
        }])
        self.assertEqual(line.billable_type, '17_subscriptions', "Revenue on a recurring product is a recurring revenue stream of its own")
        self.assertEqual(line.category_report, 'revenues')
        self.assertEqual(
            unlinked_line.billable_type, '17_subscriptions',
            "The recurring product alone decides, so a line the sales order item never got linked to is reported the same way",
        )
