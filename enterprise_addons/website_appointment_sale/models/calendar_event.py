# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    appointment_type_has_payment_step = fields.Boolean(related="appointment_type_id.has_payment_step")
    sale_order_line_ids = fields.One2many('sale.order.line', 'calendar_event_id', 'Sale Order Line')
    sale_order_count = fields.Integer('Sales Order Count', compute='_compute_sale_order_count')
    show_create_so_btn = fields.Boolean(compute='_compute_show_create_so_btn')

    def _compute_sale_order_count(self):
        sol_data = self.env['sale.order.line']._read_group(
            domain=[('calendar_event_id', 'in', self.ids)],
            groupby=['calendar_event_id'],
            aggregates=['order_id:count_distinct'],
        )
        mapped_data = {event.id: count for event, count in sol_data}
        for event in self:
            event.sale_order_count = mapped_data.get(event.id, 0)

    @api.depends('appointment_type_id', 'partner_ids')
    def _compute_show_create_so_btn(self):
        """ Only show SO creation button when a few conditions are met: the meeting must not be cancelled, have at
        least one attendee besides organizer's, linked to an appointment with payment step, not linked to any SOL
        yet and have non-null reserved capacity. The button is also hidden for a new record in creation.
        """
        for event in self:
            attendees_not_organizer = event.partner_ids - event.partner_id
            event.show_create_so_btn = (
                event.id
                and event.appointment_status != 'cancelled'
                and event.appointment_type_has_payment_step
                and not event.sale_order_line_ids
                and attendees_not_organizer
                and event.total_capacity_reserved
            )

    def action_create_sale_order(self):
        self.ensure_one()
        attendees_not_organizer = self.partner_ids - self.partner_id
        so_partner = (
            self.appointment_booker_id if self.appointment_booker_id in attendees_not_organizer
            else attendees_not_organizer[0] if attendees_not_organizer
            else self.env['res.partner']
        )
        return {
            'name': _("Create a Sale Order for %s", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event.sale.order.create',
            'target': 'new',
            'views': [[False, 'form']],
            'context': {
                'default_calendar_event_id': self.id,
                'default_partner_id': so_partner.id,
                'dialog_size': 'medium',
            },
        }
