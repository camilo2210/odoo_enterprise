from datetime import datetime
from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged, users
from .common import AppointmentCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class AppointmentCalendarEventTest(AppointmentCommon):

    @users('apt_manager')
    def test_appointment_calendar_event_inverse_capacity(self):
        """Ensure the inverse appropriately assigns bookings such that the input reserved capacity is preserved.

        If the resources cannot hold the requested capacity, an empty booking line should be added.
        In the case of appointments where capacity is not managed, the capacity should be 1 per resource selected
        regardless of their capacity.
        """
        user_appointment = self.apt_type_manage_capacity_users
        user_appointment.staff_user_ids += self.env.user

        resource_appointment = self.apt_type_resource
        resource_appointment.resource_ids = [
            (5, 0, 0),
            (0, 0, {'name': '1', 'capacity': 1}),
            (0, 0, {'name': '3', 'capacity': 3}),
            (0, 0, {'name': '5', 'capacity': 5}),
        ]
        resource_appointment.resource_ids = [(0, 0, {'name': '5 + 2', 'capacity': 2, 'linked_resource_ids': [resource_appointment.resource_ids[-1].id]})]
        base_dict = {'manage_capacity': False, 'user_capacity': 1}

        test_cases = [
            (user_appointment, {'manage_capacity': False, 'user_capacity': 5}, {}, 5, 1, 0),
            (user_appointment, {'manage_capacity': True, 'user_capacity': 5}, {}, 4, 4, 0),
            (user_appointment, {'manage_capacity': True, 'user_capacity': 5}, {}, 5, 5, 0),
            # over-booking is allowed and goes to the user
            (user_appointment, {'manage_capacity': True, 'user_capacity': 5}, {}, 6, 6, 0),
            (resource_appointment, {'manage_capacity': False}, {'resource_ids': resource_appointment.resource_ids}, 2, 4, 0),
            (resource_appointment, {'manage_capacity': False}, {'resource_ids': resource_appointment.resource_ids}, 5, 4, 0),
            (resource_appointment, {'manage_capacity': True}, {'resource_ids': resource_appointment.resource_ids}, 11, 11, 0),
            # over-booking is allowed and goes to the unassigned row
            (resource_appointment, {'manage_capacity': True}, {'resource_ids': resource_appointment.resource_ids}, 16, 16, 5),
            # no resource assigned: the whole capacity goes to the unassigned row
            (resource_appointment, {'manage_capacity': True}, {}, 11, 11, 11),
        ]

        for appointment_type, appointment_vals, event_vals, total_capacity_reserved, expected_total_capacity_reserved, expected_unassigned_capacity in test_cases:
            with self.subTest(
                appointment=appointment_type.name, appointment_vals=appointment_vals, event_vals=event_vals,
                total_capacity_reserved=total_capacity_reserved, expected_total_capacity_reserved=expected_total_capacity_reserved,
            ):
                appointment_type.write(base_dict | appointment_vals)
                calendar_event_vals = {
                    'appointment_type_id': appointment_type.id,
                    'name': 'Test Booking',
                    'total_capacity_reserved': total_capacity_reserved,
                } | event_vals
                new_event = self.env['calendar.event'].with_context(appointment_allow_overbooking=True).create(calendar_event_vals)
                new_event.invalidate_recordset(['total_capacity_reserved', 'user_id', 'resource_ids', 'booking_line_ids'])
                for event in new_event:
                    self.assertEqual(event.total_capacity_reserved, expected_total_capacity_reserved)
                    unassigned_lines = event.booking_line_ids.filtered(
                        lambda line: not line.appointment_resource_id
                        and line.appointment_type_id.schedule_based_on == 'resources'
                    )
                    self.assertEqual(len(unassigned_lines), 1 if expected_unassigned_capacity else 0)
                    self.assertEqual(
                        sum(unassigned_lines.mapped('capacity_reserved')), expected_unassigned_capacity,
                        'Overflow capacity should be kept on unassigned booking lines',
                    )
                new_event.unlink()

    @freeze_time('2022-02-14 07:00:00')
    def test_reschedule_appointment_event(self):
        """Rescheduling should update the existing event in place. Covers both
        standard and all-day appointments.
        The standard appointment type uses the Europe/Brussels timezone, while calendar
        events are stored in UTC, so an 08:00 slot is expected to be stored as 07:00.
        """
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        self.authenticate(None, None)
        customer = self.env["res.partner"].create({
            "name": "Customer Name",
            "email": "customer@test.com",
        })

        appointment_type_allday = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'category': 'custom',
            'name': 'Custom with allday slots',
            'slot_ids': [
                Command.create({
                    'allday': True,
                    'end_datetime': datetime(2022, 2, 15, 0, 0, 0),
                    'slot_type': 'unique',
                    'start_datetime': datetime(2022, 2, 15, 0, 0, 0),
                }),
                Command.create({
                    'allday': True,
                    'end_datetime': datetime(2022, 2, 17, 0, 0, 0),
                    'slot_type': 'unique',
                    'start_datetime': datetime(2022, 2, 16, 0, 0, 0),
                }),
            ],
            'staff_user_ids': [(4, self.staff_user_bxls.id)],
        })

        for appointment_type, event_vals, submit_vals, expected, expected_tracking_values in [
            (
                self.apt_type_bxls_2days,
                [(datetime(2022, 2, 14, 8, 0, 0), datetime(2022, 2, 14, 9, 0, 0), False)],
                {
                    'datetime_str': '2022-02-15 08:00:00',
                    'duration_str': '1',
                },
                {
                    'allday': False,
                    'start': '2022-02-15 07:00:00',
                    'stop': '2022-02-15 08:00:00',
                },
                {
                    'body': f'Appointment rescheduled by: {customer.name}',
                    'tracking_values': [
                        ('start', 'datetime', datetime(2022, 2, 14, 8, 0, 0), datetime(2022, 2, 15, 7, 0, 0)),
                        ('stop', 'datetime', datetime(2022, 2, 14, 9, 0, 0), datetime(2022, 2, 15, 8, 0, 0)),
                    ],
                },
            ),
            (
                appointment_type_allday,
                [(datetime(2022, 2, 15, 0, 0, 0), datetime(2022, 2, 15, 0, 0, 0), True)],
                {
                    'datetime_str': '2022-02-16 00:00:00',
                    'duration_str': '48',
                    'allday': 1,
                },
                {
                    'allday': True,
                    'start_date': fields.Date.from_string('2022-02-16'),
                    'stop_date': fields.Date.from_string('2022-02-17'),
                },
                {
                    'body': f'Appointment rescheduled by: {customer.name}',
                    'tracking_values': [
                        ('start', 'datetime', datetime(2022, 2, 15, 0, 0, 0), datetime(2022, 2, 16, 0, 0, 0)),
                        ('start_date', 'date', datetime(2022, 2, 15, 0, 0, 0), datetime(2022, 2, 16, 0, 0, 0)),
                        ('stop', 'datetime', datetime(2022, 2, 15, 0, 0, 0), datetime(2022, 2, 17, 0, 0, 0)),
                        ('stop_date', 'date', datetime(2022, 2, 15, 0, 0, 0), datetime(2022, 2, 17, 0, 0, 0)),
                    ],
                },
            ),
        ]:
            with self.subTest(appointment_type=appointment_type):
                appointment_type.is_published = True

                event = self._create_meetings(
                    self.staff_user_bxls,
                    event_vals,
                    appointment_type_id=appointment_type.id,
                    meeting_values={"appointment_booker_id": customer.id},
                    partners=customer,
                )

                original_id = event.id
                access_token = event.access_token
                original_count = self.env['calendar.event'].with_context(active_test=False).search_count([])

                with self.mock_mail_gateway(), self.mock_mail_app():
                    self.url_open(
                        f"/appointment/{appointment_type.id}/submit_reschedule",
                        data={
                            'access_token': access_token,
                            'csrf_token': self.csrf_token(),
                            'partner_id': customer.id,
                            'staff_user_id': self.staff_user_bxls.id,
                            'asked_capacity': 1,
                            **submit_vals,
                        },
                    )
                event.invalidate_recordset()

                # event is the same, correclty updated
                self.assertEqual(event.id, original_id)
                self.assertEqual(event.access_token, access_token)
                self.assertTrue(event.active)
                self.assertEqual(
                    self.env['calendar.event'].with_context(active_test=False).search_count([]),
                    original_count,
                )
                self.assertEqual(event.allday, expected['allday'])
                self.assertEqual(event.partner_ids, customer + self.staff_user_bxls.partner_id)

                if expected['allday']:
                    self.assertEqual(event.start_date, expected['start_date'])
                    self.assertEqual(event.stop_date, expected['stop_date'])
                else:
                    self.assertEqual(fields.Datetime.to_string(event.start), expected['start'])
                    self.assertEqual(fields.Datetime.to_string(event.stop), expected['stop'])

                # reschedule info logged
                self.assertEqual(len(self._new_msgs), 5, '2 invites (customer/employee), 2 date updated (customer/employee), 1 tracking')
                # tracking is rendered by the public user, whose tz is unset, hence UTC
                track = self._new_msgs[-1].with_context(tz='UTC')
                self.assertMessageFields(track, {
                    'message_type': 'tracking',
                    'subtype_id': self.env.ref('calendar.mt_calendar_event_updated'),
                    **expected_tracking_values,
                })

    def test_appointment_calendar_event_quickcreate_prefill(self):
        """Check that new records prefill the best resources, only when assignment is automatic."""
        resource_appointment = self.apt_type_resource
        resource_appointment.resource_ids = [
            (5, 0, 0),
            (0, 0, {'name': '1', 'capacity': 1}),
            (0, 0, {'name': '3', 'capacity': 3}),
        ]
        resource_appointment.manage_capacity = True

        booking_form = self.env.ref('appointment.calendar_event_view_form_gantt_booking')
        CalendarEvent = self.env['calendar.event'].with_context(
            default_appointment_type_id=resource_appointment.id,
            default_start='2010-01-01 01:00:00',
            default_stop='2010-01-01 02:00:00',
        )
        form = Form(CalendarEvent, booking_form)
        form.total_capacity_reserved = 2
        self.assertEqual(
            form.resource_ids.ids,
            resource_appointment.resource_ids[1].ids,
            'Should propose the smallest resource accommodating the asked capacity',
        )

        resource_appointment.is_auto_assign = False
        form = Form(CalendarEvent, booking_form)
        form.total_capacity_reserved = 2
        self.assertFalse(
            form.resource_ids.ids,
            'Should not suggest resources when assignment is manual',
        )

    @users('apt_manager')
    def test_appointment_calendar_event_onchange_capacity(self):
        """Cover resource selection through the capacity onchange.

        This is globally expected to set the same resources the website form would have selected
        if auto_assign is set. Note that we only ever assign 1 group, falling back onto the largest
        group of available resources. Shared resources are not part of groups unless explicitly linked.
        """
        resource_appointment = self.apt_type_resource
        resource_appointment.resource_ids = [
            (5, 0, 0),
            (0, 0, {'name': 'b1', 'capacity': 5}),
            (0, 0, {'name': 'b2', 'capacity': 2}),
            (0, 0, {'name': 'b3', 'capacity': 1}),
            (0, 0, {'name': 'b4', 'capacity': 1}),
            (0, 0, {'name': 'a', 'capacity': 10}),
            (0, 0, {'name': 'c', 'capacity': 5}),
            (0, 0, {'name': 'd', 'capacity': 3}),
        ]
        resource_a, resource_b1, resource_b2, resource_b3, resource_b4, _, resource_d = (
            resource_appointment.resource_ids.sorted('name')
        )
        resource_b1.linked_resource_ids = resource_b2 + resource_b3 + resource_b4  # group of 9
        resource_b = resource_b1 + resource_b2 + resource_b3 + resource_b4

        booking_form = self.env.ref('appointment.calendar_event_view_form_gantt_booking')
        CalendarEvent = self.env['calendar.event'].with_context(
            default_appointment_type_id=resource_appointment.id,
            default_start='2010-01-01 01:00:00',
            default_stop='2010-01-01 02:00:00',
        )
        cases = [
            # exact match of capacity for 1 resource -> pick that resource
            ('exact match, first in order', 1, resource_b3, 0),
            ('exact match', 2, resource_b2, 0),
            ('exact match outside of the group', 3, resource_d, 0),
            ('exact match, first in order (regardless of whether part of group)', 5, resource_b1, 0),
            # first resource in order covers whole capacity
            ('first fitting candidate in sequence order', 4, resource_b1, 0),
            # capacity covered by group of linked resources, pick as few as possible
            ('6 = 5 + 1', 6, resource_b1 + resource_b3, 0),
            ('7 = 5 + 2, not 5 + 1 + 1', 7, resource_b1 + resource_b2, 0),
            ('8 = 5 + 2 + 1', 8, resource_b1 + resource_b2 + resource_b3, 0),
            ('whole group', 9, resource_b, 0),
            # overbooking
            ('no group fits: largest group + overflow', 11, resource_a, 1),
            ('above total capacity: largest group + overflow', 28, resource_a, 18),
        ]
        for case_name, asked, expected_resources, expected_unassigned in cases:
            with self.subTest(case=case_name, asked=asked):
                form = Form(CalendarEvent, booking_form)
                form.total_capacity_reserved = asked
                self.assertEqual(set(form.resource_ids.ids), set(expected_resources.ids))
                self.assertEqual(form.total_capacity_unassigned, expected_unassigned)

        # Only *available* resources are selected: skip one taken by another event and one on leave.
        slot_start = fields.Datetime.from_string('2010-01-01 01:00:00')
        slot_stop = fields.Datetime.from_string('2010-01-01 02:00:00')
        self.env['calendar.event'].create({
            'appointment_type_id': resource_appointment.id,
            'name': 'Occupying booking',
            'start': slot_start,
            'stop': slot_stop,
            'resource_ids': resource_a.ids,
            'total_capacity_reserved': 10,
        })
        self.env['appointment.leave'].create({
            'leave_type': 'resources',
            'resource_ids': resource_d.ids,
            'date_from': slot_start,
            'date_to': slot_stop,
        })
        form = Form(CalendarEvent, booking_form)
        form.total_capacity_reserved = 10
        self.assertNotIn(resource_a, form.resource_ids, 'A resource fully booked by another event is skipped')
        self.assertNotIn(resource_d, form.resource_ids, 'A resource on leave is skipped')
        self.assertEqual(
            set(form.resource_ids.ids), set(resource_b.ids),
            'Selection falls back to the largest group that is still available',
        )
        self.assertEqual(
            form.total_capacity_unassigned, 1,
            'Seats that no available group can hold stay unassigned',
        )

    @users('apt_manager')
    def test_appointment_calendar_event_overbooking_requires_context(self):
        """Overbooking raises unless `appointment_allow_overbooking` in context.

        This is to be defensive in logic that may be using the inverse expecting it to
        prevent cases that would be illegal for an appointment booked via the website.

        In the backend the form view will warn users attempting to book more than possible
        but should ultimately let them do it as it is an explicit choice.
        """
        resource_appointment = self.apt_type_resource
        resource_appointment.resource_ids = [
            (5, 0, 0),
            (0, 0, {'name': '3', 'capacity': 3}),
        ]
        event_vals = {
            'appointment_type_id': resource_appointment.id,
            'name': 'Overbooked',
            'start': '2010-01-01 01:00:00',
            'stop': '2010-01-01 02:00:00',
            'total_capacity_reserved': 5,
            'resource_ids': resource_appointment.resource_ids.ids,
        }
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env['calendar.event'].create(dict(event_vals))
        event = self.env['calendar.event'].with_context(appointment_allow_overbooking=True).create(dict(event_vals))
        self.assertEqual(event.total_capacity_unassigned, 2)

    def test_appointment_calendar_event_write_capacity_manual_assign(self):
        """Check that resources are never reassigned automatically when assignment is manual."""
        resource_appointment = self.apt_type_resource
        resource_appointment.resource_ids = [
            (5, 0, 0),
            (0, 0, {'name': '3', 'capacity': 3}),
            (0, 0, {'name': '5', 'capacity': 5}),
        ]
        resource_appointment.manage_capacity = True
        resource_appointment.is_auto_assign = False

        booking = self.env['calendar.event'].with_context(appointment_allow_overbooking=True).create({
            'appointment_type_id': resource_appointment.id,
            'name': 'Test Booking for 2 people',
            'start': '2010-01-01 01:00:00',
            'stop': '2010-01-01 02:00:00',
            'resource_ids': resource_appointment.resource_ids[0],
            'total_capacity_reserved': 2,
        })

        # updating capacity or dates keeps the manually selected resources
        booking.total_capacity_reserved = 3
        self.assertEqual(booking.resource_ids, resource_appointment.resource_ids[0])
        booking.write({'start': '2010-01-01 02:00:00', 'stop': '2010-01-01 03:00:00'})
        self.assertEqual(booking.resource_ids, resource_appointment.resource_ids[0])

        # asking for more capacity than the selected resources allow is not blocked
        # but the overcapacity goes to the unassigned row
        booking.total_capacity_reserved = 4
        self.assertEqual(booking.resource_ids, resource_appointment.resource_ids[0])
        self.assertEqual(booking.total_capacity_reserved, 4)

        # (a plain create() never runs the onchange, so it has to be checked through a Form)
        booking_form = self.env.ref('appointment.calendar_event_view_form_gantt_booking')
        form = Form(self.env['calendar.event'].with_context(
            default_appointment_type_id=resource_appointment.id,
            default_start='2010-01-01 01:00:00',
            default_stop='2010-01-01 02:00:00',
        ), booking_form)
        form.total_capacity_reserved = 2
        self.assertFalse(form.resource_ids, 'Manual assignment should not suggest resources')
        self.assertEqual(form.total_capacity_unassigned, 2)
