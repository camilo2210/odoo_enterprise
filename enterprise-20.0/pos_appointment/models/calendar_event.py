# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import api, models, fields, _


class CalendarEvent(models.Model):
    _name = 'calendar.event'
    _inherit = ["calendar.event", "pos.load.mixin"]

    answers = fields.Char('Q&A answers', compute='_compute_answers')
    phone_number = fields.Char(string='Phone number')
    appointment_status = fields.Selection(group_expand='_read_group_appointment_status')
    waiting_list_capacity = fields.Integer(string='Waiting List Capacity', compute='_compute_waiting_list_capacity', store=True, readonly=False)

    @api.model
    def _read_group_appointment_status(self, status, domain):
        return ['booked', 'attended', 'no_show']

    @api.depends('appointment_answer_input_ids')
    def _compute_answers(self):
        for record in self:
            record.answers = (', ').join([answer.value_text_box or answer.value_answer_id.name for answer in record.appointment_answer_input_ids.sorted('id')])

    def _appointment_resource_domain(self, data):
        return [('booking_line_ids.appointment_resource_id', '=', False)]

    @api.model
    def _load_pos_data_domain(self, data):
        now = fields.Datetime.now()
        day_after = fields.Date.context_today(self) + timedelta(days=1)
        return (
            self._appointment_resource_domain(data)
            + [
                ('appointment_type_id', '=', data['pos.config'].appointment_type_id.id),
                '|', '&', ('start', '>=', now), ('start', '<=', day_after), '&', ('stop', '>=', now), ('stop', '<=', day_after),
            ]
        )

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'start', 'duration', 'stop', 'name', 'appointment_type_id', 'appointment_status', 'appointment_resource_ids',
                'total_capacity_reserved', 'waiting_list_capacity', 'partner_ids']

    def action_open_booking_gantt_view(self):
        user_tz = ZoneInfo(self.env.user.tz or 'UTC')
        today = datetime.now(user_tz).date()
        utc_tz = ZoneInfo('UTC')

        def to_utc(h, m=0, s=0):
            return datetime.combine(today, time(h, m, s), tzinfo=user_tz).astimezone(utc_tz)

        filter_slot_timing = {
            "morning_time": to_utc(0),
            "afternoon_time": to_utc(11),
            "evening_time": to_utc(17),
            "endday_time": to_utc(23, 59, 59),
        }

        appointment_type_id = self.env.context.get('appointment_type_id')
        return {
            'name': _('Bookings'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            "views": [
                (self.env.ref("pos_appointment.calendar_event_view_gantt_booking_resource").id, "gantt"),
                (self.env.ref("pos_appointment.calendar_event_view_kanban").id, 'kanban'),
                (self.env.ref("pos_appointment.calendar_event_view_list").id, 'list'),
                (self.env.ref("appointment.calendar_event_view_pivot").id, 'pivot'),
                (self.env.ref("pos_appointment.calendar_event_view_form_gantt_booking").id, 'form'),
                (self.env.ref("pos_appointment.calendar_event_view_graph_pos_appointment").id, 'graph'),
            ],
            'target': 'current',
            'search_view_id': (self.env.ref('pos_appointment.view_calendar_event_search').id, 'search'),
            'domain': [('appointment_type_id', '=', appointment_type_id)],
            'context': {
                'appointment_booking_gantt_show_all_resources': True,
                'active_model': 'appointment.type',
                'default_partner_ids': [],
                'default_duration': 2,
                'default_waiting_list_capacity': 2,
                'hide_no_content_helper': True,
                'from_pos_booking': True,
                'default_appointment_type_id': appointment_type_id,
                'default_name': False,
                'no_breadcrumbs': True,
                **filter_slot_timing,
            },
        }

    @api.depends('resource_ids')
    def _compute_waiting_list_capacity(self):
        for event in self:
            # always sync if capacity is managed
            if not event.waiting_list_capacity:
                if event.total_capacity_reserved:
                    event.waiting_list_capacity = event.total_capacity_reserved
                elif event.resource_ids:
                    event.waiting_list_capacity = sum(event.resource_ids.mapped('capacity'))
                else:
                    event.waiting_list_capacity = 0

    def set_attended(self):
        self.appointment_status = 'attended'

    def set_cancelled(self):
        self.appointment_status = 'cancelled'
