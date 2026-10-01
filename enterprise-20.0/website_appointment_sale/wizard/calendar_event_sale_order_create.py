from odoo import Command, fields, models


class CalendarEventSaleOrderCreate(models.TransientModel):
    _name = 'calendar.event.sale.order.create'
    _description = 'Create SO from Meeting'

    calendar_event_id = fields.Many2one("calendar.event", "Booking", required=True)
    partner_id = fields.Many2one("res.partner", "Customer", required=True)
    total_capacity_reserved = fields.Integer("Total Reserved", related="calendar_event_id.total_capacity_reserved")

    def action_create_open_sale_order(self):
        self.ensure_one()
        calendar_event = self.calendar_event_id
        appointment = calendar_event.appointment_type_id

        self.env['sale.order'].create([{
            'partner_id': self.partner_id.id,
            'order_line': [Command.create({
                'calendar_event_id': calendar_event.id,
                'product_id': appointment.product_id.id,
                'product_uom_qty': self.total_capacity_reserved,
                'name': appointment._get_booking_multiline_description(
                    calendar_event.start,
                    calendar_event.stop,
                    calendar_event.user_id if appointment.schedule_based_on == 'users' else self.env['res.users'],
                    appointment.appointment_tz
                ),
            })]
        }])
        so_action = self.action_view_sale_order()
        so_action['target'] = 'current'
        return so_action

    def action_view_sale_order(self):
        self.ensure_one()
        calendar_event = self.calendar_event_id
        action = self.env['ir.actions.actions']._for_xml_id('sale.action_orders')
        action['context'] = {'active_test': False}
        action['res_id'] = calendar_event.sale_order_line_ids[0].order_id.id if calendar_event.sale_order_line_ids else False
        action['views'] = [(False, 'form')]
        return action
