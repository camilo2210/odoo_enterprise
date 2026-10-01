# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _matches_additional_invoicing_conditions(self):
        """ Override to accept the condition when there are reward matches on subscriptions invoicing.
        This function checks if the reward line has a product that is eligible to be re-invoiced.
        :returns bool: True if the line matches the invoicing conditions, or False otherwise. """
        res = super()._matches_additional_invoicing_conditions()
        if self.is_reward_line:
            # Check if the reward itself is recurring, even if the rule is not
            recurring_rewards = self.env['loyalty.reward']._get_recurring_rewards()
            has_recurring_reward = any(self.product_id.id in reward._get_reward_products() for reward in recurring_rewards)
            res |= has_recurring_reward
        return res

    def _matches_extra_qty_update_conditions(self):
        """ Override to accept the condition for rewarding awards on subscriptions invoicing.
        This function checks if the reward line can be granted according to the product eligibility and remaining points amount.
        :returns bool: True if the line matches the quantity update conditions, or False otherwise. """
        res = super()._matches_extra_qty_update_conditions()
        if self.is_reward_line and self.order_id._has_loyalty_invoices_threshold():
            recurring_rewards = self.env['loyalty.reward']._get_recurring_rewards()
            loyalty_cards = self.env['loyalty.card'].search([('order_id', '=', self.order_id.id)])

            if recurring_rewards and loyalty_cards:
                for reward in recurring_rewards:
                    # For each recurring reward, we deduct the points or clear the promo points.
                    has_line_match = self.product_id.id in reward._get_reward_products()
                    if has_line_match:
                        for loyalty_card in loyalty_cards:
                            if loyalty_card.points - reward.required_points >= 0:
                                res = True  # Update reward quantity
                                if reward.clear_wallet:
                                    points_cleared = loyalty_card.points  # Clear promo points
                                    loyalty_card._add_history_for_subscription(self.order_id, points_issued=0, points_used=points_cleared)
                                else:
                                    loyalty_card._add_history_for_subscription(self.order_id, points_issued=0, points_used=reward.required_points)  # Deduct reward points
        return res
