from odoo import models, api


class PosPrepOrder(models.Model):
    _inherit = 'pos.prep.order'

    @api.model
    def update_last_order_change(self, order):
        existing_prep_orders = order.prep_order_ids
        super().update_last_order_change(order)
        prep_orders_added = order.prep_order_ids - existing_prep_orders
        order._send_prep_order_notifications(prep_orders_added)
