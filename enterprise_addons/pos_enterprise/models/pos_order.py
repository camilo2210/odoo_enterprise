from odoo import models, api, fields


class PosOrder(models.Model):
    _inherit = 'pos.order'
    avg_preparation_time = fields.Float(string="Preparation Time", compute="_compute_avg_time", help="Average preparation time of the order")
    avg_service_time = fields.Float(string="Service Time", compute="_compute_avg_time", help="Average service time of the order")

    def _compute_avg_time(self):
        for rec in self:
            prep_times = rec.lines.filtered(lambda line: line.preparation_time >= 0).mapped('preparation_time')
            service_times = rec.lines.filtered(lambda line: line.service_time >= 0).mapped('service_time')
            rec.avg_preparation_time = sum(prep_times) / len(prep_times) if prep_times else -1
            rec.avg_service_time = sum(service_times) / len(service_times) if service_times else -1

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['user_id', 'date_order', 'pos_reference', 'internal_note', 'preset_time', 'preset_id', 'general_customer_note', 'floating_order_name', 'tracking_number', 'uuid', 'config_id']

    @api.model
    def sync_from_ui(self, orders):
        data = super().sync_from_ui(orders)

        order_ids_for_prep_display = set()
        if len(orders) > 0:
            orders = self.browse([o['id'] for o in data["pos.order"]])
            for order in orders:
                if order.state == 'paid':
                    self.env['pos.prep.order'].update_last_order_change(order)
                    order_ids_for_prep_display.add(order.id)

        if self.env.context.get('preparation'):
            order_ids_for_prep_display.add(data["pos.order"][0]['id'])

        for orderId in order_ids_for_prep_display:
            order = self.browse(orderId)
            sound = not self.env.context.get('silent', False)
            for p_dis in order.prep_order_ids.prep_line_ids.prep_display_ids:
                p_dis._send_load_orders_message(sound, '', order.id)

        return data

    @api.ondelete(at_uninstall=False)
    def _notify_prep_display_on_order_delete(self):
        prep_displays = self.env['pos.prep.display'].search([
            '|',
            ('pos_config_ids', '=', False),
            ('pos_config_ids', 'in', self.config_id.ids)
        ])
        for prep_display in prep_displays:
            prep_display._notify('POS_ORDER_DELETED', {'pos_order_ids': self.ids})

    def action_pos_order_cancel(self):
        super().action_pos_order_cancel()
        # When an order is cancelled from the backend UI, ensure the preparation display
        # is updated to reflect the cancellation
        orders = self.browse(self.env.context.get('active_ids')).exists()
        for order in orders:
            pdis_orders = self.env['pos.prep.order'].search(
                [('pos_order_id', '=', order.id)]
            )
            pdis_lines = pdis_orders.prep_line_ids
            for line in pdis_lines:
                line.cancelled = line.quantity
            for p_dis in pdis_lines.prep_display_ids:
                p_dis._send_load_orders_message(True, '', order.id)
