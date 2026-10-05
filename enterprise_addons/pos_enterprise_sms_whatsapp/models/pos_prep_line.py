from odoo import models


class PosPrepLine(models.Model):
    _inherit = 'pos.prep.line'

    def change_prep_line_stage(self, prep_display_id, direction=1):
        """Override to send order ready notification via SMS/WhatsApp."""
        result = super().change_prep_line_stage(prep_display_id, direction)

        # Track orders we've notified to avoid duplicates
        notified_orders = set()
        prep_display = self.env['pos.prep.display'].browse(prep_display_id)

        # Send notification when order reaches second last stage (ready)
        for prep_line in self:
            if prep_line.is_second_to_last_stage:
                order = prep_line.pos_order_line_id.order_id
                if order and order.id not in notified_orders and order.partner_id and order.partner_id.phone:
                    prep_display.send_order_notifications(order, 'ready')
                    notified_orders.add(order.id)

        return result
