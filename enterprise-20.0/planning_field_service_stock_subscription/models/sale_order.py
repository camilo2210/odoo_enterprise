from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_renew_upsell_order(self, subscription_state, message_body):
        order = super()._create_renew_upsell_order(subscription_state, message_body)
        for line in order.order_line.sudo():
            if line.parent_line_id.lot_ids:
                line.lot_ids = line.parent_line_id.lot_ids
        return order
