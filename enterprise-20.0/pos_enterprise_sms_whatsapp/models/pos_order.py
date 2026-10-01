from odoo import models, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _send_prep_order_notifications(self, prep_orders_added):
        """Send 'order received' notification when new prep orders are created for the first time.
        Avoids sending multiple notifications (method can be called twice with an online PM).
        """
        if not prep_orders_added or not self.partner_id or not self.partner_id.phone:
            return
        for p_dis in prep_orders_added.prep_line_ids.prep_display_ids:
            p_dis.send_order_notifications(self, 'received')

    @api.model
    def sync_from_ui(self, orders):
        """Override to send order received notification via SMS/WhatsApp."""
        if not self.env.context.get('preparation'):
            return super().sync_from_ui(orders)

        existing_prep_orders = self.env['pos.prep.order'].search([('pos_order_id', '=', orders[0].get('id'))])

        result = super().sync_from_ui(orders)

        order_id = result.get("pos.order", [{}])[0].get('id')
        if not order_id:
            return result

        order = self.env['pos.order'].browse(order_id)
        new_prep_orders = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)])
        order._send_prep_order_notifications(new_prep_orders - existing_prep_orders)

        return result
