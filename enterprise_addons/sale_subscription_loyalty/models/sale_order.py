# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools.float_utils import float_round


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ["rating.mixin", "sale.order"]

    def _create_invoices(self, *args, **kwargs):
        """ Override to add loyalty cards points to subscription being invoiced. """
        for order in self:
            if order.is_subscription:
                order._add_points_to_subscriptions()
        invoices = super()._create_invoices(*args, **kwargs)
        for order in self:
            order_invoices = invoices & order.invoice_ids
            if order_invoices and order._has_loyalty_invoices_threshold():
                order._update_recurring_reward_discount_price(order_invoices)
        return invoices

    def _add_points_to_subscriptions(self):
        """ Add points to the loyalty cards for subscriptions invoicing after the 2nd invoice (included). """
        self.ensure_one()
        # Count invoiced subscriptions to check points addition validity.
        if not self._has_loyalty_invoices_threshold():
            return

        # Get matching rules and the loyalty card associated to the subscription for adding points.
        rules = self.env['loyalty.rule']._get_rule_matches_with_subscription_program(order_id=self)
        loyalty_cards = self.env['loyalty.card'].search([('order_id', '=', self.id)])
        if rules and loyalty_cards:
            for rule in rules:
                # Give points according to the rule's reward_point_mode.
                points = self._get_subscription_rule_points(rule)
                if not points:
                    continue
                for loyalty_card in loyalty_cards:
                    loyalty_card._add_history_for_subscription(self, points_issued=points, points_used=0)

    def _get_subscription_rule_points(self, rule):
        """ Get amount of points granted by 'rule' on each renewal, scaled per 'reward_point_mode'. """
        self.ensure_one()
        if rule.reward_point_mode == 'order':
            return rule.reward_point_amount
        valid_products = rule._get_valid_products()
        recurring_lines = self.order_line.filtered(
            lambda l: not l.is_reward_line and l.recurring_invoice
            and (not valid_products or l.product_id in valid_products)
        )
        if not recurring_lines:
            return 0
        if rule.reward_point_mode == 'unit':
            return rule.reward_point_amount * sum(recurring_lines.mapped('product_uom_qty'))
        if rule.reward_point_mode == 'money':
            return float_round(
                rule.reward_point_amount * sum(recurring_lines.mapped('price_total')),
                precision_digits=2, rounding_method='DOWN',
            )
        return 0

    def _has_loyalty_invoices_threshold(self):
        """ Returns True if subscription has at least one active invoice (posted). """
        self.ensure_one()
        return bool(self.invoice_ids.filtered(
            lambda i: i.move_type in ('out_invoice', 'out_refund') and i.state == 'posted'
        ))

    def _update_recurring_reward_discount_price(self, invoices):
        """ Recompute the price_unit of recurring percent-discount reward lines on the invoice.
        On subscription renewals, non-recurring lines are dropped but the discount was computed
        looking to the full SO, so the discount amount must be corrected to match the invoiced total. """
        for invoice in invoices:
            # Find discount reward invoice lines that are recurring
            reward_invoice_lines = invoice.invoice_line_ids.filtered(
                lambda line: line.sale_line_ids[:1].reward_id.filtered(
                    lambda r: r.reward_type == 'discount' and r.recurring_invoice and r.discount_mode == 'percent'
                )
            )
            if not reward_invoice_lines:
                continue

            # The discount is split into one SO/invoice line per tax group, so we cannot simply
            # set a single price_unit. Instead, we scale each split line by the ratio of the new
            # invoiced subtotal to the original one, preserving each line's proportional share.
            non_reward_lines = invoice.invoice_line_ids.filtered(
                lambda line: not line.sale_line_ids[:1].reward_id
            )
            reward = reward_invoice_lines.sale_line_ids[:1].reward_id
            if reward.discount_applicability == 'specific':
                # Filter the non reward lines by checking the specific products specified in the discount condition.
                domain = reward._get_discount_product_domain()
                discount_product_ids = self.env["product.product"]._search(domain)
                non_reward_lines = non_reward_lines.filtered(lambda l: l.product_id.id in discount_product_ids)
            invoiced_subtotal = sum(non_reward_lines.mapped('price_subtotal'))
            original_discount_total = sum(reward_invoice_lines.mapped('price_unit'))
            if original_discount_total:
                if not invoiced_subtotal:
                    reward_invoice_lines.unlink()
                    continue
                new_discount_total = -(invoiced_subtotal * reward.discount / 100.0)
                ratio = new_discount_total / original_discount_total

                # Apply the proportional recalculated discount to the reward line.
                for reward_line in reward_invoice_lines:
                    reward_line.price_unit *= ratio
