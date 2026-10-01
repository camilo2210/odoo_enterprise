# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    def _add_history_for_subscription(self, order, points_issued=0, points_used=0):
        """Create loyalty history record(s) for a subscription order.

        :param sale.order order: the subscription order
        :param float points_issued: points granted to the card
        :param float points_used: points deducted from the card
        """
        self.ensure_one()
        LoyaltyHistory = self.env['loyalty.history']
        base_values = {
            'order_model': order._name,
            'order_id': order.id,
            'description': 'Subscription %s' % order.display_name,
        }
        # Award before consuming: the consumed points are drawn from the awarded ones.
        for points in (points_issued, -points_used):
            LoyaltyHistory.create(
                LoyaltyHistory._get_history_lines_values(self, base_values, points)
            )
