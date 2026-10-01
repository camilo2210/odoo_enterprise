# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, timedelta
from collections import defaultdict
from markupsafe import Markup
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models, tools, SUPERUSER_ID
from odoo.addons.calendar.models.utils import interval_from_events
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Domain
from odoo.tools.intervals import Intervals, intervals_overlap, invert_intervals
from odoo.tools.date_utils import localized
from odoo.tools.mail import email_normalize, email_split_and_format_normalize, html_sanitize

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        # If the event has an apt type, set the event stop datetime to match the apt type duration
        if res.get('appointment_type_id') and res.get('duration') and res.get('start') and 'stop' in fields and "default_stop" not in self.env.context:
            res['stop'] = res['start'] + timedelta(hours=res['duration'])
        if not self.env.context.get('booking_gantt_create_record', False):
            return res
        # Round the stop datetime to the nearest minute when coming from the gantt view
        if res.get('stop') and isinstance(res['stop'], datetime) and res['stop'].second != 0:
            res['stop'] = datetime.min + round((res['stop'] - datetime.min) / timedelta(minutes=1)) * timedelta(minutes=1)
        user_id = res.get('user_id')
        appointment_resource_ids = self.env['calendar.event']._fields['resource_ids'].convert_to_cache(res.get('resource_ids', []), self.env['calendar.event'])
        appointment_resources = self.env['appointment.resource'].browse(appointment_resource_ids)
        # get a relevant appointment type for ease of use when coming from a view that groups by resource
        if not res.get('appointment_type_id') and 'appointment_type_id' in fields:
            appointment_types = False
            if appointment_resources:
                appointment_types = appointment_resources.appointment_type_ids
            elif user_id:
                appointment_types = self.env['appointment.type'].search([('staff_user_ids', 'in', user_id)])
            if appointment_types:
                res['appointment_type_id'] = appointment_types[0].id

        if (appointment_type_id := res.get('appointment_type_id')):
            appointment_type = self.env['appointment.type'].browse(appointment_type_id)
            # set the maximum capacity if managing capacities
            if 'total_capacity_reserved' in fields:
                if appointment_type.schedule_based_on == 'resources':
                    res.setdefault(
                        'total_capacity_reserved',
                        sum(resource.capacity for resource in appointment_resources) or 2
                        if appointment_type.manage_capacity else
                        len(appointment_resources) or 1
                    )
                elif appointment_type.schedule_based_on == 'users':
                    res.setdefault(
                        'total_capacity_reserved',
                        (appointment_type.manage_capacity and appointment_type.user_capacity) or 1
                    )

        if self.env.context.get('appointment_default_assign_user_attendees'):
            default_partner_ids = self.env.context.get('default_partner_ids', [])
            # If there is only one attendee -> set him as organizer of the calendar event
            # Mostly used when you click on a specific slot in the appointment kanban
            if default_partner_ids and len(default_partner_ids) == 1 and 'user_id' in fields:
                attendee_user = self.env['res.partner'].browse(default_partner_ids).user_ids
                if attendee_user:
                    res['user_id'] = attendee_user[0].id
            # Special gantt case: we want to assign the current user to the attendees if he's set as organizer
            elif res.get('user_id') and res.get('partner_ids', Command.set([])) == [Command.set([])] and \
                res['user_id'] == self.env.uid and 'partner_ids' in fields:
                res['partner_ids'] = [Command.set(self.env.user.partner_id.ids)]
        return res

    name = fields.Char(compute='_compute_name', store=True, readonly=False)
    location = fields.Char(compute='_compute_location', store=True, readonly=False)

    appointment_answer_input_ids = fields.One2many('appointment.answer.input', 'calendar_event_id', string="Appointment Answers")
    appointment_status = fields.Selection([
        ('request', 'Request'),
        ('booked', 'Booked'),
        ('attended', 'Checked-In'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
    ], string="Appointment Status", compute='_compute_appointment_status', store=True, readonly=False, tracking=True)
    appointment_type_id = fields.Many2one('appointment.type', 'Appointment', index='btree_not_null', tracking=True)
    appointment_type_schedule_based_on = fields.Selection(related="appointment_type_id.schedule_based_on")
    appointment_type_manage_capacity = fields.Boolean(related="appointment_type_id.manage_capacity")
    appointment_type_staff_user_ids = fields.Many2many(related="appointment_type_id.staff_user_ids")
    appointment_invite_id = fields.Many2one('appointment.invite', 'Appointment Invitation', readonly=True, index='btree_not_null', ondelete='set null')
    appointment_resource_ids = fields.Many2many('appointment.resource', 'appointment_booking_line', 'calendar_event_id', 'appointment_resource_id',
                                                string="Appointment Resources", group_expand="_read_group_appointment_resource_ids",
                                                depends=['booking_line_ids'], readonly=True, copy=False)
    appointment_fields_can_edit = fields.Boolean(compute='_compute_appointment_fields_can_edit')
    # This field is used in the form view to create/manage the booking lines based on the total_capacity_reserved
    # selected. This allows to have the appointment_resource_ids field linked to the appointment_booking_line model and
    # thus avoid the duplication of information.
    resource_ids = fields.Many2many('appointment.resource', string="Resources",
                                    compute="_compute_resource_ids", inverse="_inverse_resource_ids_or_capacity",
                                    search="_search_resource_ids",
                                    falsy_value_label="Unassigned",
                                    group_expand="_read_group_appointment_resource_ids", copy=False)
    booking_line_ids = fields.One2many('appointment.booking.line', 'calendar_event_id', string="Booking Lines", copy=True)
    partner_ids = fields.Many2many('res.partner', group_expand="_read_group_partner_ids")
    total_capacity_reserved = fields.Integer('Total Capacity Reserved', compute="_compute_total_capacity", inverse="_inverse_resource_ids_or_capacity")
    total_capacity_unassigned = fields.Integer('Missing Seats', compute="_compute_total_capacity_unassigned", compute_sudo=True)
    total_capacity_used = fields.Integer('Total Capacity Used', compute="_compute_total_capacity")
    user_id = fields.Many2one('res.users', group_expand="_read_group_user_id")
    videocall_redirection = fields.Char('Meeting redirection URL', compute='_compute_videocall_redirection')
    appointment_booker_id = fields.Many2one('res.partner', string="Person who is booking the appointment", index='btree_not_null')
    unavailable_resource_ids = fields.Many2many('appointment.resource', string='Resources intersecting with leave time', compute="_compute_unavailable_resource_ids")
    require_appointment_feedback_mail = fields.Boolean(string="Require feedback mail", copy=False)

    _check_no_draft_bookings = models.Constraint(
        'CHECK(appointment_type_id IS NULL OR NOT is_draft)',
        'A event with an appointment_type_id cannot be a draft.',
    )

    @api.constrains('appointment_resource_ids', 'appointment_type_id')
    def _check_resource_and_appointment_type(self):
        for event in self:
            if event.appointment_resource_ids and not event.appointment_type_id:
                raise ValidationError(_("The event %s cannot book resources without an appointment type.", event.name))

    @api.constrains('appointment_type_id', 'appointment_status')
    def _check_status_and_appointment_type(self):
        for event in self:
            if event.appointment_status and not event.appointment_type_id:
                raise ValidationError(_("The event %s cannot have an appointment status without being linked to an appointment type.", event.name))

    def _check_organizer_validation_conditions(self, vals_list):
        res = super()._check_organizer_validation_conditions(vals_list)
        appointment_type_ids = list({vals["appointment_type_id"] for vals in vals_list if vals.get("appointment_type_id")})

        if appointment_type_ids:
            appointment_type_ids = self.env['appointment.type'].browse(appointment_type_ids)
            resource_appointment_type_ids = set(appointment_type_ids.filtered(lambda apt: apt.schedule_based_on == 'resources').ids)

            return [vals.get("appointment_type_id") not in resource_appointment_type_ids for vals in vals_list]

        return res

    @api.depends('allday', 'appointment_type_id')
    def _compute_alarm_ids(self):
        bookings_wt_alarms = self.filtered(lambda e: e.appointment_type_id and not e.alarm_ids)
        for event in bookings_wt_alarms:
            event.alarm_ids = event.appointment_type_id.reminder_ids
        super(CalendarEvent, self - bookings_wt_alarms)._compute_alarm_ids()

    @api.depends('appointment_type_id')
    def _compute_appointment_status(self):
        for event in self:
            if not event.appointment_type_id:
                event.appointment_status = False
            elif not event.appointment_status:
                event.appointment_status = 'booked'

    @api.depends_context('uid')
    def _compute_appointment_fields_can_edit(self):
        for event in self:
            # Only users with appointment rights or the organizer (must be a staff user) of the event can edit the appointment fields.
            event.appointment_fields_can_edit = self.env.user.has_groups('appointment.group_appointment_user') or event.user_id == self.env.user

    def _compute_user_can_edit(self):
        super()._compute_user_can_edit()
        if self.env.user.has_groups('appointment.group_appointment_resource_user'):
            self.filtered(lambda e: e.appointment_type_id and e.appointment_type_schedule_based_on == 'resources').user_can_edit = True

    @api.depends('appointment_type_id', 'appointment_type_schedule_based_on')
    def _compute_calendar_id(self):
        # Never automatically assign a calendar to resource bookings.
        # If the user manually assigns a calendar to a resource booking, do not override it.
        resource_events = self.filtered(
            lambda e: e.appointment_type_id and e.appointment_type_schedule_based_on == "resources"
        )
        super(CalendarEvent, self - resource_events)._compute_calendar_id()

    @api.depends('appointment_type_id')
    def _compute_location(self):
        for event in self.filtered('appointment_type_id'):
            event.location = event.appointment_type_id.location

    @api.depends('partner_ids')
    def _compute_name(self):
        for event in self.filtered(lambda e: e.appointment_type_id and not e.name):
            non_staff_attendees = event.partner_ids.filtered(
                lambda p: p._origin.id not in event.appointment_type_id.staff_user_ids.partner_id.ids
            )
            if len(non_staff_attendees) == 1:
                event.name = non_staff_attendees.name + " - " + event.appointment_type_id.name

    @api.depends('booking_line_ids', 'booking_line_ids.appointment_resource_id')
    def _compute_resource_ids(self):
        for event in self:
            event.resource_ids = event.booking_line_ids.appointment_resource_id

    @api.onchange('total_capacity_reserved', 'appointment_type_id')
    def _onchange_total_capacity_reserved(self):
        """Assign the best resources depending on the capacity requested.

        Users are still able to force a value if they wish but the assumption is that
        they will prefer resources that fits properly over keeping the current ones.
        """
        for event in self.filtered(lambda event:
            event.appointment_type_schedule_based_on == 'resources'
            and event.appointment_type_manage_capacity
            and event.appointment_type_id.sudo().is_auto_assign
        ):
            capacity_to_reserve = event.total_capacity_reserved
            # skip if resources fit capacity, does not account for shareable resources potentially having different capacities
            if sum(event.resource_ids.mapped('capacity')) >= capacity_to_reserve:
                continue
            if (
                capacity_to_reserve <= 0
                or event.appointment_type_schedule_based_on != 'resources'
                or not event.start or not event.stop
            ):
                continue
            resource_info = event.appointment_type_id.with_context(
                ignore_event_ids=event.ids,
            )._get_resources_for_capacity(capacity_to_reserve, event.start, event.stop)
            suggested_resource_ids = [resource.id for resource in resource_info]
            if suggested_resource_ids:
                event.resource_ids = suggested_resource_ids

    def _compute_unavailable_partner_ids(self):
        super()._compute_unavailable_partner_ids()
        for start, stop, events in interval_from_events(self.filtered(lambda e: e.appointment_type_id)):
            users = events.partner_ids.user_ids
            if not users:
                continue
            leaves_by_user_id = self.env['appointment.leave'].sudo()._get_appointment_leave_intervals(
                start, stop, staff_users=users, appointment_types=events.appointment_type_id,
            )
            for event in events:
                for user in event.partner_ids.user_ids:
                    if leaves_by_user_id.get(user, []):
                        event.unavailable_partner_ids |= user.partner_id

    @api.depends('start', 'stop', 'resource_ids')
    def _compute_unavailable_resource_ids(self):
        self.unavailable_resource_ids = False
        resource_events = self.filtered(lambda event: event.resource_ids)
        if not resource_events:
            return

        for start, stop, events in interval_from_events(resource_events):
            events_by_appointment = events.grouped('appointment_type_id')
            events_outside_slots = self.env['calendar.event']
            for appointment_type, appt_events in events_by_appointment.items():
                # Hack to handle case when event start is too close to the slot start for which
                # the _slot_generate skips the first slot due to min_schedule_hours.
                slot_generate_start = localized(start) - timedelta(hours=appointment_type.appointment_duration)
                if slot_generate_start <= datetime.now(ZoneInfo('UTC')) + timedelta(hours=appointment_type.min_schedule_hours):
                    slot_generate_start -= timedelta(hours=appointment_type.min_schedule_hours)
                slot_intervals = Intervals(
                    (
                        (slot["utc"][0], slot["utc"][1], slot["slot"])
                        for slot in appointment_type._slots_generate(
                            localized(slot_generate_start),
                            localized(stop),
                            "utc",
                            reference_date=localized(slot_generate_start),
                        )
                    ),
                    keep_distinct=True,
                )
                for event in appt_events:
                    event.unavailable_resource_ids = self.env['appointment.resource']
                    event_interval = Intervals([(localized(event.start), localized(event.stop), self.env['appointment.slot'])])
                    if event_interval - slot_intervals:
                        events_outside_slots |= event
                        event.unavailable_resource_ids = event.resource_ids
                    else:
                        overlapping_intervals = slot_intervals & event_interval
                        available_resources = event.resource_ids._origin.filtered(
                            lambda resource: all(
                                resource in slot.restrict_to_resource_ids
                                for _, _, slot in overlapping_intervals
                                if slot.restrict_to_resource_ids
                            )
                        )
                        event.unavailable_resource_ids = event.resource_ids._origin - available_resources

            events -= events_outside_slots
            group_resources = events.resource_ids
            availabilities_values = events.appointment_type_id._slot_availability_prepare_resources_values(
                group_resources, start, stop)
            resource_unavailabilities = availabilities_values['resource_to_apt_leaves']
            resource_to_bookings = availabilities_values['resource_to_bookings']

            events_to_check = self.env['calendar.event']
            for resource, bookings in resource_to_bookings.items():
                booking_events = bookings.calendar_event_id
                events_manage_capacity = booking_events.mapped('appointment_type_manage_capacity')
                isAllCapacityTrue = all(events_manage_capacity)
                isAllCapacityFalse = not any(events_manage_capacity)
                # Add events of the bookings to check if:
                # - There are event appointments with manage capacity True and False
                # - Manage capacity is all True and resource is not shareable or capacity used > resource capacity
                # - Manage capacity is all False and more than one appointment type or number of bookings > max_bookings
                if (
                    (not isAllCapacityTrue and not isAllCapacityFalse) or
                    (isAllCapacityTrue and (sum(bookings.mapped('capacity_used')) >= resource.capacity or not resource.shareable)) or
                    (isAllCapacityFalse and (len(bookings.appointment_type_id) > 1 or len(bookings) > bookings.appointment_type_id.max_bookings))
                ):
                    events_to_check |= booking_events
            for event in events:
                event_resources = event.resource_ids
                event_interval = (localized(event.start), localized(event.stop))
                event.unavailable_resource_ids |= event_resources.filtered(lambda resource: any(
                    intervals_overlap((localized(start), localized(stop)), event_interval)
                    for start, stop, _ in resource_unavailabilities.get(resource, [])
                ))
                for conflicting_event in events_to_check - event._origin:
                    if (
                        (resources := event_resources._origin & conflicting_event.resource_ids)
                        and intervals_overlap(event_interval, (localized(conflicting_event.start), localized(conflicting_event.stop)))
                    ):
                        event.unavailable_resource_ids |= resources

    @api.depends('booking_line_ids')
    def _compute_total_capacity(self):
        booking_data = self.env['appointment.booking.line']._read_group(
            [('calendar_event_id', 'in', self.ids)],
            ['calendar_event_id'],
            ['capacity_reserved:sum', 'capacity_used:sum'],
        )
        mapped_data = {
            meeting.id: {
                'total_capacity_reserved': total_capacity_reserved,
                'total_capacity_used': total_capacity_used,
            } for meeting, total_capacity_reserved, total_capacity_used in booking_data}

        for event in self:
            data = mapped_data.get(event.id)
            event.total_capacity_reserved = data.get('total_capacity_reserved', 0) if data else 0
            event.total_capacity_used = data.get('total_capacity_used', 0) if data else 0

    @api.depends('booking_line_ids.appointment_resource_id', 'booking_line_ids.capacity_reserved', 'appointment_type_id', 'resource_ids', 'total_capacity_reserved')
    def _compute_total_capacity_unassigned(self):
        """Capacity reserved that is not assigned to any resource.

        For user appointments, this is the difference between the total capacity and the max capacity per user.

        For resource appointments, this is either the sum of capacity reserved in unassigned rows.
        Or the difference between the total capacity and the sum of resource capacities (ignoring unavailabilities)
        if the recordset contains NewIds, indicating we cannot rely on inverses logic having run yet.
        """
        self.total_capacity_unassigned = 0
        capacity_managed_events = self.filtered('appointment_type_manage_capacity')
        # if onchange (e.g. in a form) compute based on computed fields to immediately reflect the result of the inverse
        if self and isinstance(self[0].id, api.NewId):
            for event in capacity_managed_events.filtered(
                lambda event: event.appointment_type_schedule_based_on == 'resources'
            ):
                event.total_capacity_unassigned = max(0, event.total_capacity_reserved - sum(resource.capacity for resource in event.resource_ids))
            for event in capacity_managed_events.filtered(
                lambda event: event.appointment_type_schedule_based_on == 'users'
            ):
                event.total_capacity_unassigned = max(0, event.total_capacity_reserved - event.appointment_type_id.user_capacity)
        else:
            grouped_events = capacity_managed_events.grouped('appointment_type_schedule_based_on')
            overcapacity_by_event = {}
            if resource_events := grouped_events.get('resources'):
                overcapacity_by_event |= dict(self.env['appointment.booking.line']._read_group(
                    domain=[('calendar_event_id', 'in', resource_events.ids), ('appointment_resource_id', '=', False)],
                    groupby=['calendar_event_id'],
                    aggregates=['capacity_reserved:sum']
                ))
            if user_events := grouped_events.get('users'):
                for max_capacity, events in user_events.grouped(lambda event: event.appointment_type_id.user_capacity).items():
                    for event in events:
                        overcapacity_by_event[event] = max(0, event.total_capacity_reserved - max_capacity)
            for event, overcapacity in overcapacity_by_event.items():
                event.total_capacity_unassigned = overcapacity

    @api.depends('videocall_location', 'access_token')
    def _compute_videocall_redirection(self):
        for event in self:
            if not event.videocall_location:
                event.videocall_redirection = False
                continue
            access_token = event._calendar_event_ensure_token()
            event.videocall_redirection = f"{event.get_base_url()}/calendar/videocall/{access_token}"

    @api.depends('appointment_type_id.event_videocall_source')
    def _compute_videocall_source(self):
        events_no_appointment = self.env['calendar.event']
        for event in self:
            if not event.appointment_type_id or event.videocall_location and not self.DISCUSS_ROUTE in event.videocall_location:
                events_no_appointment |= event
                continue
            event.videocall_source = event.sudo().appointment_type_id.event_videocall_source
        super(CalendarEvent, events_no_appointment)._compute_videocall_source()

    @api.depends_context('show_calendar_event_name_with_count')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('show_calendar_event_name_with_count'):
            return
        for event in self.filtered(lambda e: e.appointment_type_id and e.appointment_type_manage_capacity):
            icon = '\U0001FA91' if event.appointment_type_schedule_based_on == 'resources' else '\U0001F464'
            event.display_name = f'{event.display_name} - {event.total_capacity_reserved}{icon}'

    def _compute_is_highlighted(self):
        super(CalendarEvent, self)._compute_is_highlighted()
        if self.env.context.get('active_model') == 'appointment.type':
            appointment_type_id = self.env.context.get('active_id')
            for event in self:
                if event.appointment_type_id.id == appointment_type_id:
                    event.is_highlighted = True

    def get_base_url(self):
        if self.appointment_type_id:
            return self.appointment_type_id.sudo().get_base_url()
        return super().get_base_url()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('appointment_type_id'):
                if 'active' not in vals and vals.get('appointment_status') == 'cancelled':
                    vals['active'] = False
                elif 'appointment_status' not in vals and vals.get('active') is False:
                    vals['appointment_status'] = 'cancelled'
        return super().create(vals_list)

    def write(self, vals):
        if any(event.appointment_type_id for event in self) or vals.get('appointment_type_id'):
            if 'active' in vals and 'appointment_status' not in vals:
                vals['appointment_status'] = 'booked' if vals['active'] else 'cancelled'
            if 'active' not in vals and 'appointment_status' in vals:
                vals['active'] = vals['appointment_status'] != 'cancelled'

        events_requiring_feedback = self.env['calendar.event']
        if vals.get('appointment_status') == 'attended':
            events_requiring_feedback = self.filtered(
                lambda e: e.appointment_status != 'attended' and e.appointment_type_id.feedback_mail_template_id
            )
        result = super(CalendarEvent, events_requiring_feedback).write(vals | {'require_appointment_feedback_mail': True})
        return result and super(CalendarEvent, self - events_requiring_feedback).write(vals)

    def _is_partner_unavailable(self, partner, partner_events):
        self.ensure_one()
        appointment = self.appointment_type_id
        if (partner in appointment.staff_user_ids.partner_id and
            not partner_events.filtered(lambda event: event.appointment_type_id != appointment)):
            max_capacity = appointment.user_capacity if appointment.manage_capacity else appointment.max_bookings
            return sum(partner_events.mapped('total_capacity_used')) > max_capacity

        return super()._is_partner_unavailable(partner, partner_events)

    def _inverse_resource_ids_or_capacity(self):
        """Update booking lines as inverse of both resource capacity and resource_ids.

        As both values are related to the booking line and resource capacity is dependant
        on resources existing in the first place. They need to both use the same inverse
        field to ensure there is no ordering conflict.
        """
        booking_lines = []
        booking_lines_to_delete = self.env['appointment.booking.line']
        for event in self:
            # for now only allow overbooking for users who are actually allowed to freely edit this event and create booking lines
            # to avoid any issues with routes that may rely on this
            user_allow_overbooking = event.sudo(False).has_access('write') and self.env['appointment.booking.line'].sudo(False).has_access('create')
            if event.appointment_type_schedule_based_on == 'resources':
                allow_overbooking = (
                    self.env.context.get('appointment_allow_overbooking')
                    # keep allowing overbooking if it was already allowed prior
                    or any(not line.appointment_resource_id for line in event.booking_line_ids if line.capacity_reserved)
                ) and user_allow_overbooking

                resources = event.resource_ids
                if event.appointment_type_manage_capacity and event.total_capacity_reserved:
                    capacity_to_reserve = event.total_capacity_reserved
                elif event.appointment_type_manage_capacity:
                    capacity_to_reserve = sum(event.booking_line_ids.mapped('capacity_reserved')) or sum(resources.mapped('capacity'))
                else:
                    capacity_to_reserve = len(event.resource_ids)
                booking_lines_to_delete |= event.booking_line_ids
                for resource in resources.sorted("shareable"):
                    if event.appointment_type_manage_capacity and capacity_to_reserve <= 0:
                        break
                    resource_capacity_used = min(resource.capacity, capacity_to_reserve) if event.appointment_type_manage_capacity else 1
                    booking_lines.append({
                        'appointment_resource_id': resource.id,
                        'calendar_event_id': event.id,
                        'capacity_reserved': resource_capacity_used,
                    })
                    capacity_to_reserve -= resource_capacity_used
                    capacity_to_reserve = max(0, capacity_to_reserve)
                if event.appointment_type_manage_capacity and capacity_to_reserve:
                    if allow_overbooking:
                        booking_lines.append({
                            'calendar_event_id': event.id,
                            'capacity_reserved': capacity_to_reserve,
                        })
                    else:
                        raise UserError(_(
                            "%(capacity)d seats are missing to be able to book the %(appointment_name)s: %(event_name)s (%(event_id)s)",
                            capacity=capacity_to_reserve, appointment_name=event.appointment_type_id.name,
                            event_name=event.name, event_id=repr(event.id),
                        ))
            elif event.appointment_type_schedule_based_on == 'users':
                max_user_capacity = (event.appointment_type_manage_capacity and event.appointment_type_id.user_capacity) or 1
                # keep allowing overbooking if it was already allowed prior
                allow_overbooking = (
                    self.env.context.get('appointment_allow_overbooking')
                    or sum(event.booking_line_ids.mapped('capacity_reserved')) > max_user_capacity
                ) and user_allow_overbooking
                if event.appointment_type_manage_capacity and event.total_capacity_reserved:
                    capacity_to_reserve = event.total_capacity_reserved
                else:
                    capacity_to_reserve = max_user_capacity
                if not allow_overbooking and event.appointment_type_manage_capacity and max_user_capacity < capacity_to_reserve:
                    raise UserError(_(
                        "%(capacity)d seats are missing to be able to book the %(appointment_name)s: %(event_name)s (%(event_id)s)",
                        capacity=capacity_to_reserve - event.appointment_type_id.user_capacity,
                        appointment_name=event.appointment_type_id.name, event_name=event.display_name, event_id=repr(event.id)
                    ))
                booking_lines_to_delete += event.booking_line_ids
                booking_lines.append({
                    'calendar_event_id': event.id,
                    'capacity_reserved': capacity_to_reserve,
                })
        booking_lines_to_delete.unlink()
        self.env['appointment.booking.line'].sudo().create(booking_lines)

    def _search_resource_ids(self, operator, value):
        return [('appointment_resource_ids', operator, value)]

    def _read_group_groupby(self, table, groupby_spec):
        """ Simulate group_by on resource_ids by using appointment_resource_ids.
            appointment_resource_ids is only used to store the data through the appointment_booking_line
            table. All computation on the resources and the capacity reserved is done with capacity_reserved.
            Simulating the group_by on resource_ids also avoids to do weird override in JS on appointment_resource_ids.
            This is needed because when simply writing on the field, it tries to create the corresponding booking line
            with the field capacity_reserved required leading to ValidationError.
        """
        if groupby_spec == 'resource_ids':
            groupby_spec = 'appointment_resource_ids'
        return super()._read_group_groupby(table, groupby_spec)

    def _read_group_appointment_resource_ids(self, resources, domain):
        if not self.env.context.get('appointment_booking_gantt_show_all_resources'):
            return resources
        resources_domain = [
            ('appointment_type_ids', '!=', False), '|', ('company_id', '=', False), ('company_id', 'in', self.env.context.get('allowed_company_ids', [])),
        ]
        # If we have a default appointment type, we only want to show those resources
        default_appointment_type = self.env.context.get('default_appointment_type_id')
        if default_appointment_type:
            return self.env['appointment.type'].browse(default_appointment_type).resource_ids.filtered_domain(resources_domain)
        return self.env['appointment.resource'].search(resources_domain)

    def _read_group_partner_ids(self, partners, domain):
        """Show the partners associated with relevant staff users in appointment gantt context."""
        if not self.env.context.get('appointment_booking_gantt_show_all_resources'):
            return partners
        appointment_type_id = self.env.context.get('default_appointment_type_id', False)
        appointment_types = self.env['appointment.type'].browse(appointment_type_id)
        if appointment_types:
            return appointment_types.staff_user_ids.partner_id
        return self.env['appointment.type'].search([('schedule_based_on', '=', 'users')]).staff_user_ids.partner_id

    def _read_group_user_id(self, users, domain):
        if not self.env.context.get('appointment_booking_gantt_show_all_resources'):
            return users
        appointment_types = self.env['appointment.type'].browse(self.env.context.get('default_appointment_type_id', []))
        if appointment_types:
            return appointment_types.staff_user_ids
        return self.env['appointment.type'].search([('schedule_based_on', '=', 'users')]).staff_user_ids

    def _track_log_get_default_body(self, track_init_values):
        if self.appointment_type_id and 'active' in track_init_values:
            if self.active:
                return _('Appointment re-booked')
            else:
                return _("Appointment cancelled")
        return super()._track_log_get_default_body(track_init_values)

    def action_cancel_meeting(self, partner_ids):
        """ In case there are more than two attendees (responsible + another attendee),
            we do not want to archive the calendar.event.
            We'll just remove the attendee(s) that made the cancellation request
        """
        self.ensure_one()
        message_body = _("Appointment cancelled")
        if partner_ids:
            attendees = self.env['calendar.attendee'].search([('event_id', '=', self.id), ('partner_id', 'in', partner_ids)])
            if attendees:
                cancelling_attendees = ", ".join([attendee.display_name for attendee in attendees])
                message_body = _("Appointment cancelled by: %(partners)s", partners=cancelling_attendees)
        self._track_set_log_message(message_body)
        # Use the organizer if set or fallback on SUPERUSER to notify attendees that the event is archived
        self.with_user(self.user_id or SUPERUSER_ID).sudo().action_archive()

    def action_set_appointment_attended(self):
        self.ensure_one()
        self.appointment_status = 'attended'

    def action_set_appointment_booked(self):
        self.ensure_one()
        self.appointment_status = 'booked'

    def action_set_appointment_cancelled(self):
        self.ensure_one()
        self.appointment_status = 'cancelled'

    def action_set_appointment_no_show(self):
        self.ensure_one()
        self.appointment_status = 'no_show'

    def _find_or_create_partners(self, guest_emails_str):
        """Used to find the partners from the emails strings and creates partners if not found.
        :param str guest_emails: optional line-separated guest emails. It will
          fetch or create partners to add them as event attendees;
        :returns: partners (recordset)"""
        # Split and normalize guest emails
        formatted_emails = email_split_and_format_normalize(guest_emails_str)
        valid_normalized = list(tools.misc.unique(email_normalize(email_input, strict=False) for email_input in formatted_emails))
        if not valid_normalized:
            return self.env['res.partner']
        # limit public usage of guests
        if self.env.su and len(valid_normalized) > 10:
            raise ValueError(
                _('Guest usage is limited to 10 customers for performance reason.')
            )

        # Find or create existing partners
        return self.env['mail.thread']._partner_find_from_emails_single(formatted_emails)

    def _get_mail_tz(self):
        self.ensure_one()
        if not self.event_tz and self.appointment_type_id.appointment_tz:
            return self.appointment_type_id.appointment_tz
        return super()._get_mail_tz()

    def _get_public_fields(self):
        return super()._get_public_fields() | {
            'appointment_resource_ids',
            'appointment_type_id',
            'resource_ids',
            'total_capacity_reserved',
            'total_capacity_used',
        }

    def _track_template_parameters(self, tracked_fields):
        res = super()._track_template_parameters(tracked_fields)
        if not self.appointment_type_id:
            return res

        appointment_type_sudo = self.appointment_type_id.sudo()
        # set 'author_id' and 'email_from' based on the organizer
        vals = {'author_id': self.user_id.partner_id.id, 'email_from': self.user_id.email_formatted} if self.user_id else {}

        if {'appointment_status', 'appointment_type_id'} & set(tracked_fields) and self.appointment_status in ['booked', 'request']:
            try:
                booking_template = self.env.ref('appointment.appointment_booking_mail_template')
            except ValueError as e:
                _logger.warning("Mail could not be sent, as mail template is not found : %s", e)
            else:
                subtype = 'appointment.mt_calendar_event_requested' if self.appointment_status == 'request' else 'appointment.mt_calendar_event_booked'
                res['appointment_type_id'] = (booking_template.sudo(), {
                    **vals,
                    'subtype_id': self.env['ir.model.data']._xmlid_to_res_id(subtype),
                })
        # Meeting cancel mail
        if (
            'active' in tracked_fields and not self.active and self.start > fields.Datetime.now()
            and appointment_type_sudo.canceled_mail_template_id
        ):
            res['active'] = (appointment_type_sudo.canceled_mail_template_id, {
                **vals,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('appointment.mt_calendar_event_canceled'),
                'notify_author': True,
            })
        return res

    @api.model
    def _cron_send_feedback_emails(self, days_delta=1, limit=500):
        time_threshold = self.env.cr.now() - timedelta(days=days_delta)

        ready_events = self.search([
            ('appointment_status', '=', 'attended'),
            ('stop', '<=', time_threshold),
            ('appointment_type_id.feedback_mail_template_id', '!=', False),
            ('require_appointment_feedback_mail', '=', True),
            ('appointment_booker_id', '!=', False),
        ], limit=limit)

        if not ready_events:
            return True

        self.env['ir.cron']._commit_progress(remaining=len(ready_events))

        for event in ready_events:
            event.rating_send_request(
                event.appointment_type_id.feedback_mail_template_id,
                lang=event.appointment_booker_id.lang,
                force_send=False,
            )

        ready_events.require_appointment_feedback_mail = False

        self.env['ir.cron']._commit_progress(processed=len(ready_events))

        if len(ready_events) == limit:
            self.env.ref('appointment.ir_cron_appointment_send_feedback_emails')._trigger()

        return True

    def _rating_get_partner(self):
        self.ensure_one()
        return self.appointment_booker_id

    def _rating_get_parent_field_name(self):
        return 'appointment_type_id'

    def _get_customer_description(self):
        # Description should make sense for the person who booked the meeting
        if not self.appointment_type_id:
            return super()._get_customer_description()

        confirmation_html = html_sanitize(self.appointment_type_id.sudo().message_confirmation or '')
        base_url = self.appointment_type_id.sudo().get_base_url()
        url = f"{base_url}/calendar/view/{self.access_token}"
        link_html = Markup("<span>%s <a href=%s>%s</a></span>") % (_("Need to reschedule?"), url, _("Click here"))

        return Markup("").join([
            self.description,
            Markup('<br>'),
            confirmation_html,
            link_html,
        ])

    @api.model
    def _get_activity_excluded_models(self):
        return super()._get_activity_excluded_models() + ['appointment.type']

    def _get_customer_summary(self):
        # Summary should make sense for the person who booked the meeting
        if self.appointment_type_id and self.appointment_type_id.schedule_based_on == 'users' and self.partner_id:
            return _('%(appointment_name)s with %(partner_name)s',
                     appointment_name=self.appointment_type_id.name,
                     partner_name=self.partner_id.name or _('somebody'))
        return super()._get_customer_summary()

    def _get_default_privacy_domain(self):
        """
        Resource related events need to be visible and accessible from the gantt view no matter their privacy.
        The privacy of an event is related to the user settings but resource events aren't typically linked to any user
        meaning their visiblity shouldn't depend on the privacy field.
        Returns:
            The formatted_read_group privacy domain adapted to include every events related to a resource appointment type.
        """
        domain = super()._get_default_privacy_domain()
        return Domain.OR([domain, [
            '&',
            ('appointment_type_id', '!=', False),
            ('appointment_type_id.schedule_based_on', '=', 'resources')
        ]])

    def _get_new_invited_attendees(self, current_attendees, previous_attendees, update_vals):
        """Notify every attendee for active appointments, except sometimes the current user."""
        # in the manual confirmation case (usually one event at a time) there is no need
        # to notify the author who just confirmed it
        if (
            update_vals.get('appointment_status') == 'booked' and
            not any(event.appointment_type_id.sudo().is_always_confirm for event in self)
        ):
            return current_attendees.with_context(mail_notify_author=False)
        if update_vals.get('appointment_status') in ('booked', 'request'):
            return current_attendees
        return super()._get_new_invited_attendees(current_attendees, previous_attendees, update_vals)

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        # skip if not dealing with appointments
        if field not in ('resource_ids', 'partner_ids'):
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)

        # if viewing a specific appointment type generate unavailable intervals outside of the defined slots
        slots_unavailable_intervals = []
        # slots unavailable due to restrictions (i.e. restrict_to_user_ids)
        unavailable_intervals_per_res_id = {}
        appointment_type = self.env['appointment.type']
        if appointment_type_id := self.env.context.get('default_appointment_type_id'):
            appointment_type = appointment_type.browse(appointment_type_id)

        if appointment_type:
            start_utc = localized(start)
            stop_utc = localized(stop)
            slot_available_intervals = []
            for slot in appointment_type._slots_generate(start_utc, stop_utc, 'utc', reference_date=start):
                if restricted_ids := slot['slot'].restrict_to_user_ids.partner_id or slot['slot'].restrict_to_resource_ids:
                    for res_id in (set(res_ids) - set(restricted_ids.ids)):
                        unavailable_intervals_per_res_id.setdefault(res_id, []).append((slot['utc'][0], slot['utc'][1]))
                slot_available_intervals.append((slot['utc'][0], slot['utc'][1]))

            slots_unavailable_intervals = invert_intervals(slot_available_intervals, start_utc, stop_utc)

        # in staff view, add conflicting events and staff appointment leaves to unavailabilities and return
        if field == 'partner_ids':
            result = {}
            partners = self.env['res.partner'].browse(res_ids)
            partner_unavailabilities = self._gantt_unavailabilities_events(start, stop, partners)
            apt_leave_intervals_per_user = self.env['appointment.leave'].sudo()._get_appointment_leave_intervals(
                start, stop, staff_users=partners.user_ids, appointment_types=appointment_type,
            )
            apt_leave_partner_intervals = defaultdict(list)
            for user, intervals in apt_leave_intervals_per_user.items():
                apt_leave_partner_intervals[user.partner_id.id].extend((start, end, user.partner_id) for start, end, _ in intervals)

            for res_id in res_ids:
                unavailabilities = partner_unavailabilities.get(res_id, Intervals([]))
                unavailabilities |= Intervals(apt_leave_partner_intervals.get(res_id, []))
                unavailabilities |= Intervals([(start, stop, self.env['res.partner']) for start, stop in slots_unavailable_intervals])
                unavailabilities |= Intervals([(start, stop, self.env['res.partner']) for start, stop in unavailable_intervals_per_res_id.get(res_id, [])])
                result[res_id] = [{'start': start, 'stop': stop} for start, stop, _ in unavailabilities]
            return result

        appointment_resource_ids = self.env['appointment.resource'].browse(res_ids)
        # in multi-company, if people can't access some of the resources we don't really care
        if self.env.context.get('allowed_company_ids'):
            appointment_resource_ids = appointment_resource_ids.filtered_domain([
                '|', ('company_id', '=', False), ('company_id', 'in', self.env.context['allowed_company_ids'])]
            )

        availabilities_values = appointment_type._slot_availability_prepare_resources_values(
            appointment_resource_ids, start, stop)
        resource_unavailabilities = availabilities_values['resource_to_apt_leaves']
        resource_to_bookings = availabilities_values['resource_to_bookings']

        # Exclude resources that are shareable but not fully occupied
        resource_unavailability_by_bookings = {resource: interval_from_events(bookings.calendar_event_id)
            for resource, bookings in resource_to_bookings.items() if not resource.shareable or not (sum(bookings.mapped('capacity_reserved')) < resource.capacity)}

        result = {False: [{'start': start, 'stop': stop} for start, stop in slots_unavailable_intervals]}
        for appointment_resource_id in appointment_resource_ids:
            unavailabilities = Intervals([(start, stop, set()) for start, stop in slots_unavailable_intervals])
            unavailabilities |= Intervals([
                (start, stop, set())
                for start, stop, _ in resource_unavailabilities.get(appointment_resource_id, [])])
            unavailabilities |= Intervals([(start, stop, set()) for start, stop in unavailable_intervals_per_res_id.get(appointment_resource_id.id, [])])
            if event_intervals := resource_unavailability_by_bookings.get(appointment_resource_id):
                unavailabilities |= Intervals([(localized(start), localized(stop), set()) for start, stop, _ in event_intervals])
            result[appointment_resource_id.id] = [{'start': start, 'stop': stop} for start, stop, _ in unavailabilities]
        return result

    def _gantt_unavailabilities_events(self, start, stop, partners):
        """Get a mapping from partner id to unavailabilities based on existing events.

        :returns: {5: Intervals([(monday_morning, monday_noon, <res.partner>(5))])}
        :rtype: dict[int, Intervals[<res.partner>]]
        """
        events = partners._get_busy_calendar_events(start, stop)
        return {
            attendee.id: Intervals([
                (localized(event.start), localized(event.stop), attendee)
                for event in events.get(attendee.id, [])
            ])
            for attendee in partners
        }

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        """Filter out rows where the partner isn't linked to an staff user, and add bookings with unassigned capacity in the "unassigned" row."""
        gantt_data = super().get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)
        if self.env.context.get('appointment_booking_gantt_show_all_resources') and groupby and groupby[0] == 'partner_ids':
            staff_partner_ids = self.env['appointment.type'].search([('schedule_based_on', '=', 'users')]).staff_user_ids.partner_id.ids
            gantt_data['groups'] = [group for group in gantt_data['groups'] if not group.get('partner_ids') or group['partner_ids'][0] in staff_partner_ids]
            # add bookings where none of the staff is as partner
            falsy_group = next((group for group in gantt_data['groups'] if not group.get('partner_ids')), None)
            if falsy_group is None:
                falsy_group = {'partner_ids': False, '__record_ids': []}
                gantt_data['groups'].insert(0, falsy_group)
            event_ids = [record['id'] for record in gantt_data['records']]
            unassigned_staff_event_ids = self.env['calendar.event'].with_context(prefetch_fields=False).search([
                ('id', 'in', event_ids),
                ('partner_ids', '!=', False),  # would already be inside the falsy group
                ('partner_ids', 'not any', [('id', 'in', staff_partner_ids)]),
            ]).ids
            falsy_group['__record_ids'].extend(unassigned_staff_event_ids)
        elif groupby and groupby[0] == 'resource_ids':
            # The falsy row would normally only include events that have no linked resource at all.
            # However we also want to show events that have empty booking lines, to highlight that
            # some seats are actually unassigned and the event needs to be handled specially
            event_ids = [record['id'] for record in gantt_data['records']]
            unassigned_line_events = self.env['calendar.event'].with_context(prefetch_fields=False).search([
                ('id', 'in', event_ids),
                ('booking_line_ids', 'any', [('appointment_resource_id', '=', False)]),
                ('booking_line_ids', 'any', [('appointment_resource_id', '!=', False)]),  # if it has no assigned line, it's already in the falsy group
            ])
            if unassigned_line_events:
                falsy_group = next((group for group in gantt_data['groups'] if not group.get('resource_ids')), None)
                if falsy_group is None:
                    falsy_group = {'resource_ids': False, '__record_ids': []}
                    gantt_data['groups'].insert(0, falsy_group)
                falsy_group['__record_ids'].extend(unassigned_line_events.ids)
        return gantt_data
