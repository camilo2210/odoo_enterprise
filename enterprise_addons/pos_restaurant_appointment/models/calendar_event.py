# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import timedelta

from odoo import api, models, fields, Command


class CalendarEvent(models.Model):
    _name = 'calendar.event'
    _inherit = 'calendar.event'

    available_capacity = fields.Integer(string="Available Capacity", compute='_compute_available_capacity', help="Used to determine current total available capacity")
    is_conflicted = fields.Boolean(string="Is Conflicted", compute='_compute_is_conflicted')

    @api.depends('appointment_type_id.resource_ids', 'appointment_type_id.meeting_ids', 'start')
    def _compute_available_capacity(self):
        now = fields.Datetime.now()
        now_plus_2 = now + timedelta(hours=2)

        for record in self:
            if not record.appointment_type_id:
                record.available_capacity = 0
                continue
            available_resources = record.appointment_type_id.with_context(start_date=record.start).get_available_appointment_resources()
            occupied_resources = record.appointment_type_id.with_context(
                start_date=fields.Datetime.to_string(record.start)
                ).resource_ids - available_resources

            event_ids = set()
            assigned_capacity = 0

            for resource in occupied_resources.filtered(lambda r: r.is_used):
                event_start = fields.Datetime.from_string(resource.is_used.get('event_start'))
                event_stop = fields.Datetime.from_string(resource.is_used.get('event_stop'))

                if (now <= event_start < now_plus_2) or (now <= event_stop < now_plus_2):
                    event_id = resource.is_used.get('event_id')
                    if event_id not in event_ids:
                        event_ids.add(event_id)
                        assigned_capacity += int(resource.is_used.get('total_capacity', 0)) - int(resource.is_used.get('capacity', 0))

            record.available_capacity = record.appointment_type_id.resource_total_capacity - assigned_capacity

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['available_capacity']

    @api.model
    def _send_table_notifications(self, command):
        today = fields.Date.context_today(self)
        config_events_map = defaultdict(lambda: self.env['calendar.event'])

        for event in self:
            # Don't include the event if it's not for today
            if event.start.date() != today:
                continue

            # tables that are booked for this event
            event_table_ids = event.booking_line_ids.appointment_resource_id.sudo().pos_table_ids
            configs = event_table_ids.mapped('floor_id.pos_config_ids')

            for config in configs:
                if (
                    config.current_session_id
                    and config.appointment_type_id
                    and config.appointment_type_id.id == event.appointment_type_id.id
                ):
                    config_events_map[config] |= event

        for config, events in config_events_map.items():
            config._notify((
                'TABLE_BOOKING',
                {
                    'command': command,
                    'data': {
                        'calendar.event': self._load_pos_data_read(events, config),
                        'res.partner': self.env['res.partner']._load_pos_data_read(events.partner_ids, config),
                    },
                },
            ))

    @api.model_create_multi
    def create(self, vals_list):
        new_events = super().create(vals_list)
        new_events._send_table_notifications("ADDED")
        return new_events

    def write(self, vals):
        self._send_table_notifications("REMOVED")
        events_removed_all_resources = []
        is_from_pos = self.env.context.get('from_pos_booking')

        if is_from_pos and 'resource_ids' in vals:
            resources_to_remove = {
                r[1] for r in vals['resource_ids']
                if isinstance(r, (list, tuple)) and r[0] == Command.UNLINK
            } if vals.get('resource_ids', []) else set()
            for event in self:
                if resources_to_remove:
                    event.booking_line_ids.filtered(lambda l: l.appointment_resource_id.id in resources_to_remove).unlink()
                elif not vals['resource_ids']:
                    event.booking_line_ids.unlink()
                if not event.booking_line_ids:
                    events_removed_all_resources.append(event.id)
        result = super().write(vals)
        booking_lines = []

        if is_from_pos and vals.get('resource_ids'):
            for event in self.filtered(lambda e: e.id not in events_removed_all_resources):
                resources = event._get_event_resources()
                event.booking_line_ids.unlink()
                booking_lines.extend([
                    {
                        'appointment_resource_id': resource.id,
                        'calendar_event_id': event.id,
                        'capacity_reserved': resource.capacity,
                    } for resource in resources
                ])
            if booking_lines:
                self.env['appointment.booking.line'].sudo().create(booking_lines)
        self._send_table_notifications("ADDED")
        return result

    def unlink(self):
        self._send_table_notifications("REMOVED")
        return super().unlink()

    @api.model
    def _appointment_resource_domain(self, data):
        if data['pos.config'].module_pos_restaurant:
            return [
                ('booking_line_ids.appointment_resource_id', 'in', data['restaurant.table'].appointment_resource_id.ids)
            ]
        else:
            return super()._appointment_resource_domain(data)

    @api.onchange('waiting_list_capacity')
    def _onchange_waiting_list_capacity(self):
        for event in self:
            if 'default_resource_ids' in self.env.context:
                default_resources = self.env['appointment.resource'].browse(self.env.context.get('default_resource_ids', []))
                event.waiting_list_capacity = 0 if default_resources else event.waiting_list_capacity
                event.resource_ids = default_resources
            else:
                event.resource_ids = event._get_event_resources()

    def _get_event_resources(self):
        self.ensure_one()
        appointment_type = self.appointment_type_id
        if not appointment_type or not self.start or not self.stop:
            return self.env['appointment.resource']
        resource_info = appointment_type.with_context(ignore_event_ids=self.ids)._get_resources_for_capacity(
            self.waiting_list_capacity, self.start, self.stop,
        )
        return self.env['appointment.resource'].browse(sorted(resource.id for resource in resource_info))

    def _compute_is_conflicted(self):
        for event in self:
            if not event.resource_ids:
                event.is_conflicted = False
                continue

            domain = [
                ('id', '!=', event.id),
                ('resource_ids', 'in', event.resource_ids.ids),
                ('start', '<', event.stop),
                ('stop', '>', event.start),
            ]
            event.is_conflicted = bool(event.search_count(domain))

    def assign_available_resources_to_event(self, config_id, resource_id):
        self.ensure_one()
        config = self.env['pos.config'].browse(config_id)
        resources = self._get_event_resources()
        self.booking_line_ids.filtered(lambda l: l.appointment_resource_id.id == resource_id).unlink()
        self.resource_ids |= resources
        return {
            'calendar.event': self._load_pos_data_read(self, config),
            'appointment.resource': self.env['appointment.resource']._load_pos_data_read(self.resource_ids, config),
        }

    def swap_resources_between_events(self, destination_event_id, config_id):
        self.ensure_one()
        config = self.env['pos.config'].browse(config_id)
        destination_event = self.browse(destination_event_id)
        source_resource_ids = self.resource_ids
        destination_resource_ids = destination_event.resource_ids
        self.booking_line_ids.unlink()
        destination_event.booking_line_ids.unlink()
        self.resource_ids = destination_resource_ids
        destination_event.resource_ids = source_resource_ids
        return {
            'calendar.event': self._load_pos_data_read(self | destination_event, config),
            'appointment.resource': self.env['appointment.resource']._load_pos_data_read(self.resource_ids | destination_event.resource_ids, config),
        }

    def reassign_resources_to_event(self, existing_event_id, resource_id, config_id):
        self.ensure_one()
        config = self.env['pos.config'].browse(config_id)
        existing_event = self.browse(existing_event_id)
        resources = self.env['appointment.resource'].browse(resource_id)
        existing_event.booking_line_ids.filtered(lambda l: l.appointment_resource_id.id == resource_id).unlink()
        existing_event.total_capacity_reserved = sum(existing_event.resource_ids.mapped('capacity'))
        self.booking_line_ids.unlink()
        self.resource_ids |= resources
        return {
            'calendar.event': self._load_pos_data_read(self | existing_event, config),
            'appointment.resource': self.env['appointment.resource']._load_pos_data_read(self.resource_ids | existing_event.resource_ids, config),
        }
