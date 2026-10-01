from odoo import models
from odoo.addons.pos_enterprise.utils.date_utils import compute_seconds_since


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    def _get_pos_orders(self):
        self.ensure_one()
        if len(self.stage_ids) <= 1:
            return {"done": [], "notDone": []}
        second_last_stage = self.stage_ids[-2]  # order will be displayed as ready.
        pdis_line_ids = self.env['pos.prep.line'].search([*self.get_preparation_display_orders_domain(), ('stage_id', '!=', self.stage_ids[-1].id)])

        # Prefetch the relational chain to avoid repeated lazy-load queries.
        pdis_line_ids.mapped('prep_order_id.pos_order_id')

        # Group lines by pos_order_id to avoid O(n²) inner loop.
        order_lines = {}
        for line in pdis_line_ids:
            pos_order = line.prep_order_id.pos_order_id
            order_lines.setdefault(pos_order.id, []).append(line)

        orders_completed = set()
        orders_not_completed = set()
        orders_completed_ready_date = {}

        for lines in order_lines.values():
            all_ready = all(line.stage_id == second_last_stage for line in lines)
            if all_ready:
                # Use the latest stage change as the order ready date.
                ready_line = max(lines, key=lambda line: line.last_stage_change)
                order_ready_date = ready_line.last_stage_change
                order_ready_delay = int(compute_seconds_since(order_ready_date) / 60)
                is_order_visible = not self.auto_clear or order_ready_delay < self.clear_time_interval
                if is_order_visible:
                    tracking_ref = lines[0].prep_order_id.pos_order_id.tracking_number
                    orders_completed.add(tracking_ref)
                    orders_completed_ready_date[tracking_ref] = str(order_ready_date)
            else:
                tracking_ref = lines[0].prep_order_id.pos_order_id.tracking_number
                orders_not_completed.add(tracking_ref)

        return {
            "done": list(orders_completed),
            "notDone": list(orders_not_completed),
            "ordersCompletedReadyDate": orders_completed_ready_date,
        }

    def _send_orders_to_customer_display(self):
        self.ensure_one()
        self._notify("NEW_ORDERS", [])

    def _send_load_orders_message(self, sound=False, notification=None, orderId=None):
        super()._send_load_orders_message(sound, notification, orderId)
        self._send_orders_to_customer_display()

    def open_customer_display(self):
        return {
            "type": "ir.actions.act_url",
            "url": f"/pos-order-tracking?access_token={self.access_token}",
            "target": "new",
        }
