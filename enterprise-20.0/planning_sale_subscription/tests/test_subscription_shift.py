from datetime import datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('-at_install', 'post_install')
class TestSubscriptionShift(TestSubscriptionCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.quick_ref('planning.group_planning_manager')
        cls.planning_role_junior = cls.env['planning.role'].create({
            'name': 'Junior Developer'
        })
        cls.product_no_recurrence, cls.product_recurrence = cls.env['product.template'].create([{
            'name': 'Product No Recurrence',
            'type': 'service',
            'planning_enabled': True,
        }, {
            'name': 'Product Recurrence',
            'recurring_invoice': True,
            'type': 'service',
            'planning_enabled': True,
            'planning_role_id': cls.planning_role_junior.id,
        }])

    def test_subscription_shift_recurrence_generation(self):
        Order = self.env['sale.order']
        OrderLine = self.env['sale.order.line']
        for product in [
            self.product_no_recurrence,
            self.product_recurrence,
        ]:
            is_recurrent = product.recurring_invoice
            for end_date in fields.Date.today() + relativedelta(months=1), False:
                order = Order.create({
                    'note': "original subscription description",
                    'partner_id': self.partner.id,
                    **({
                           'is_subscription': True,
                           'plan_id': self.plan_month.id,
                           'end_date': end_date,
                       } if is_recurrent else {}),
                })
                order_line = OrderLine.create({
                    'order_id': order.id,
                    'product_id': product.product_variant_id.id,
                })
                order.action_confirm()
                if not is_recurrent:
                    self.assertFalse(order_line.planning_slot_ids.recurrency_id,
                        "The shift created should not be recurrent if the product is not recurrent")
                    continue

                self.assertTrue(order_line.planning_slot_ids.recurrency_id,
                        "The shift created should be recurrent if the product is recurrent")
                shift_recurrence = order_line.planning_slot_ids.recurrency_id
                if end_date:
                    self.assertEqual(shift_recurrence.repeat_type, 'until',
                        "A subscription with an end date must create a shift with a recurrence of type 'until'")
                    self.assertEqual(shift_recurrence.repeat_until.date(), end_date,
                        "A subscription with an end date must set its end date on its shift's recurrence")
                else:
                    self.assertEqual(shift_recurrence.repeat_type, 'forever',
                        "No end date on the subscription must result in a shift with a recurrence of type 'forever'")

    def test_recurring_shift_plan_update(self):
        order = self.env['sale.order'].create({
            'is_subscription': True,
            'note': "original subscription description",
            'partner_id': self.partner.id,
            'plan_id': self.plan_week.id,
        })
        order_lines = self.env['sale.order.line'].create([{
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }, {
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }, {
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }])
        order.action_confirm()
        for line in order_lines:
            self.assertEqual(line.planning_slot_ids.recurrency_id.repeat_unit, 'week')
            self.assertEqual(line.planning_slot_ids.recurrency_id.repeat_interval, 1)
        order.plan_id = self.plan_2_month
        for line in order_lines:
            self.assertEqual(line.planning_slot_ids.recurrency_id.repeat_unit, 'month')
            self.assertEqual(line.planning_slot_ids.recurrency_id.repeat_interval, 2)

    @freeze_time("2026-09-5")
    def test_recurring_shift_subscription_update(self):
        order = self.env['sale.order'].create({
            'is_subscription': True,
            'note': "original subscription description",
            'partner_id': self.partner.id,
            'plan_id': self.plan_month.id,
        })
        order_lines = self.env['sale.order.line'].create([{
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }, {
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }, {
            'order_id': order.id,
            'product_id': self.product_recurrence.product_variant_id.id,
        }])
        order.action_confirm()
        self.assertEqual(len(order_lines.planning_slot_ids), 18, "18 (3*6) shifts should be created as the datestart limit is 6 months in the future.")
        order.end_date = fields.Date.today() + relativedelta(weeks=1)
        self.assertEqual(len(order_lines.planning_slot_ids), 3, "Only the first shift of each line should be left as the other shifts are planned later than the new end date.")
        for line in order_lines:
            self.assertEqual(line.planning_slot_ids.recurrency_id.repeat_type, 'until')
            self.assertEqual(line.planning_slot_ids.recurrency_id.repeat_until, datetime.combine(order.end_date, datetime.min.time()))
