# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.tools import SQL


class ReportPosOrder(models.Model):
    _inherit = "report.pos.order"

    delivery_provider_id = fields.Many2one(
        'pos.delivery.provider',
        string='Food delivery Aggregator',
        readonly=True,
        help="Delivery provider for online orders, e.g., UberEats, Zomato."
    )
    average_prep_time = fields.Float(
        string='Average Preparation Time',
        readonly=True,
        aggregator="avg",
        help="Average preparation time for orders with delivery providers."
    )
    urbanpiper_canceled_order_count = fields.Integer(
        string='Reject Food delivery orders',
        readonly=True,
        help="Count of canceled urbanpiper orders."
    )

    def _select(self):
        return SQL("""%s,
            s.delivery_provider_id AS delivery_provider_id,
            s.preparation_time AS average_prep_time,
            CASE
                WHEN s.delivery_status = 'cancelled' THEN 1
                ELSE 0
            END AS urbanpiper_canceled_order_count
        """, super()._select())

    def _group_by(self):
        return SQL("""%s,
            s.delivery_provider_id
        """, super()._group_by())
