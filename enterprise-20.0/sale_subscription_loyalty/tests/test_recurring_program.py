# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, freeze_time
from odoo import Command
from odoo.addons.sale_subscription.tests.common_sale_subscription import TestSubscriptionCommon


@tagged('post_install', '-at_install')
class TestSubscriptionLoyalty(TestSubscriptionCommon):
    _test_user_groups = None  # FIXME list needed groups

    def setUp(self):
        super().setUp()
        self.sub_program = self.env['loyalty.program'].create({
            'name': 'Subscription Loyalty Program (101 points per invoice)',
            'trigger': 'auto',
            'program_type': 'promotion',
            'applies_on': 'both',
            'rule_ids': [Command.create({
                'product_ids': self.product, 'reward_point_mode': 'order',
                'reward_point_amount': 101,
                'minimum_qty': 1,
                'recurring_invoice': True,  # Make it recurring on subscription invoicing.
            })],
            'reward_ids': [Command.create({
                'reward_type': 'discount', 'discount': 10,
                'required_points': 1, 'discount_mode': 'percent',
                'discount_applicability': 'order',
                'recurring_invoice': True,  # Make it recurring on subscription invoicing.
            })],
        })

    def test_program_applied_subscription_invoices(self):
        """ Ensure that recurring rules and rewards are applied on sub invoicing. """
        with freeze_time("2021-01-01"):
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub.order_line = [Command.create({
                'product_id': self.product.id, 'name': "product",
                'price_unit': 42, 'product_uom_qty': 2,
            })]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2029-02-02'})
            sub.action_confirm()

            self.assertTrue(all(not l.is_reward_line for l in sub.order_line), "No reward should be added yet.")
            sub.action_open_reward_wizard()
            reward_line = sub.order_line.filtered(lambda l: l.is_reward_line)
            self.assertTrue(reward_line and reward_line.product_uom_qty == 1, "Reward must be added after action execution.")

            invoice_1 = sub._create_invoices()
            invoice_1.action_post()
            card = self.env['loyalty.card'].search([('order_id', '=', sub.id)])
            self.assertEqual(card.points, 100, "Points must be 100, as 101 (gained) - 1 (spent) = 100 pts.")

            invoice_2 = sub._create_invoices()
            invoice_2.action_post()
            self.assertEqual(card.points, 200, "Points must now be 200, as 100 + 101 (new gain) - 1 (new expense) = 200 pts.")

    def test_discount_recalculated_on_renewal_without_non_recurring_line(self):
        """ Ensure the percent discount is recalculated on the 2nd invoice based only on recurring lines. """
        with freeze_time("2021-01-01"):
            non_recurring_product = self.env['product.product'].create({
                'name': 'One-shot Product', 'type': 'service',
                'recurring_invoice': False, 'list_price': 100,
                'property_account_income_id': self.product.property_account_income_id.id,
            })
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub.order_line = [
                Command.create({'product_id': self.product.id, 'name': "Recurring", 'price_unit': 50, 'product_uom_qty': 1}),
                Command.create({'product_id': non_recurring_product.id, 'name': "One-shot", 'price_unit': 100, 'product_uom_qty': 1}),
            ]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2029-02-02'})
            sub.action_confirm()
            sub.action_open_reward_wizard()

            # First invoice: discount applies on 50 + 100 = 150 => -15.
            invoice_1 = sub._create_invoices()
            invoice_1.action_post()
            reward_lines_1 = invoice_1.invoice_line_ids.filtered(lambda l: l.sale_line_ids[:1].reward_id)
            self.assertAlmostEqual(sum(reward_lines_1.mapped('price_unit')), -15, "First invoice: 10% of 150 = -15.")

            # Second invoice: only the recurring line (50) is present => discount must be -5.
            invoice_2 = sub._create_invoices()
            reward_lines_2 = invoice_2.invoice_line_ids.filtered(lambda l: l.sale_line_ids[:1].reward_id)
            self.assertAlmostEqual(sum(reward_lines_2.mapped('price_unit')), -5, "Second invoice: 10% of 50 = -5.")

    def test_discount_recalculated_on_renewal_specific_product(self):
        """ Ensure the percent discount on specific product is recalculated or removed on the 2nd invoice. """
        with freeze_time("2021-01-01"):
            non_recurring_product = self.env['product.product'].create({
                'name': 'One-shot Product', 'type': 'service',
                'recurring_invoice': False, 'list_price': 100,
                'property_account_income_id': self.product.property_account_income_id.id,
            })
            self.sub_program.reward_ids.write({
                'discount_applicability': 'specific',
                'discount_product_ids': [Command.set(non_recurring_product.ids)],
            })
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub.order_line = [
                Command.create({'product_id': self.product.id, 'name': "Recurring", 'price_unit': 50, 'product_uom_qty': 1}),
                Command.create({'product_id': non_recurring_product.id, 'name': "One-shot", 'price_unit': 100, 'product_uom_qty': 1}),
            ]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2029-02-02'})
            sub.action_confirm()
            sub.action_open_reward_wizard()

            # First invoice: discount applies only on non_recurring_product (100) => -10.
            invoice_1 = sub._create_invoices()
            invoice_1.action_post()
            reward_lines_1 = invoice_1.invoice_line_ids.filtered(lambda l: l.sale_line_ids[:1].reward_id)
            self.assertAlmostEqual(sum(reward_lines_1.mapped('price_unit')), -10, "First invoice: 10% of 100 = -10.")

            # Second invoice: only the recurring line (50) is present, none of the specific discount product => no discount.
            invoice_2 = sub._create_invoices()
            reward_lines_2 = invoice_2.invoice_line_ids.filtered(lambda l: l.sale_line_ids[:1].reward_id)
            self.assertFalse(reward_lines_2, "Reward should be removed when subtotal of specific products is 0.")

    def test_recurring_rule_follow_reward_point_mode(self):
        """ Recurring rules with reward_point_mode 'unit' or 'money' must multiply points
        with the recurring lines rather than always granting a flat reward_point_amount. """
        with freeze_time("2021-01-01"):
            self.sub_program.rule_ids.write({
                'reward_point_mode': 'unit',
                'reward_point_amount': 2,
            })
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub.order_line = [Command.create({
                'product_id': self.product.id, 'name': "product",
                'price_unit': 42, 'product_uom_qty': 3,
            })]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2029-02-02'})
            sub.action_confirm()
            sub.action_open_reward_wizard()

            invoice_1 = sub._create_invoices()
            invoice_1.action_post()
            card = self.env['loyalty.card'].search([('order_id', '=', sub.id)])
            # First invoice grants no new recurring points (already issued at confirmation).
            points_after_first_invoice = card.points

            invoice_2 = sub._create_invoices()
            invoice_2.action_post()
            # Second invoice: rule grants 2 pts * 3 units = 6, reward consumes 1 => net +5.
            self.assertEqual(
                card.points,
                points_after_first_invoice + 6 - 1,
                "Recurring rule in 'unit' mode must grant reward_point_amount * recurring qty.",
            )

    def test_recurring_rule_grants_points_without_reward_line(self):
        """ A recurring rule must grant its points on each renewal even when the
        subscription has no reward line in its order (rule independent of reward). """
        with freeze_time("2021-01-01"):
            # Drop the recurring flag on the reward so only the rule is recurring.
            self.sub_program.reward_ids.recurring_invoice = False
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub.order_line = [Command.create({
                'product_id': self.product.id, 'name': "product",
                'price_unit': 42, 'product_uom_qty': 1,
            })]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2029-02-02'})
            sub.action_confirm()
            # Intentionally skip action_open_reward_wizard: no reward line on the order.

            invoice_1 = sub._create_invoices()
            invoice_1.action_post()
            card = self.env['loyalty.card'].search([('order_id', '=', sub.id)])
            points_after_first_invoice = card.points

            invoice_2 = sub._create_invoices()
            invoice_2.action_post()
            # Second invoice triggers the recurring rule alone and grants its 101 pts.
            self.assertEqual(
                card.points,
                points_after_first_invoice + 101,
                "Recurring rule must grant points on renewals even without a reward line on the order.",
            )

    def test_recurring_reward_not_invoiced_with_negative_quantity(self):
        """ A recurring reward must not be invoiced with a negative quantity once
        the loyalty card has run out of points to cover its required_points. """
        with freeze_time("2021-01-01"):
            # Single initial grant of 2 pts so the card empties after two reward consumptions.
            self.sub_program.rule_ids.write({
                'recurring_invoice': False,
                'reward_point_amount': 2,
            })
            sub = self.subscription
            sub.order_line = [Command.clear()]
            sub.order_line = [Command.create({
                'product_id': self.product.id, 'name': "product",
                'price_unit': 42, 'product_uom_qty': 1,
            })]
            sub.write({'start_date': False, 'next_invoice_date': False, 'end_date': '2029-02-02'})
            sub.action_confirm()
            sub.action_open_reward_wizard()

            # 2 pts issued at confirmation, 1 consumed at reward claim => 1 left.
            # Invoice 1 is before the threshold (no posted invoice yet), so no deduction.
            # Invoice 2 is after the threshold and deducts the remaining point.
            sub._create_invoices().action_post()
            sub._create_invoices().action_post()
            card = self.env['loyalty.card'].search([('order_id', '=', sub.id)])
            self.assertEqual(card.points, 0, "Card should be empty after the second invoice consumes the last point.")

            # Third invoice: card has 0 pts so the recurring reward cannot be re-granted.
            # The reward line must be capped at qty 0, not invoiced with a negative qty.
            invoice_3 = sub._create_invoices()
            reward_lines_3 = invoice_3.invoice_line_ids.filtered(lambda l: l.sale_line_ids[:1].reward_id)
            for line in reward_lines_3:
                self.assertGreaterEqual(
                    line.quantity, 0,
                    "Reward line must not be invoiced with a negative quantity when the card is empty.",
                )
