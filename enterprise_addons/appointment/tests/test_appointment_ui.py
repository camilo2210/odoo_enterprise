# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from odoo import Command
from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import common, tagged, users
from odoo.tools import float_compare
from odoo.tools.misc import mute_logger


class AppointmentUICommon(AppointmentCommon, common.HttpCase):

    @classmethod
    def setUpClass(cls):
        super(AppointmentUICommon, cls).setUpClass()

        cls.env.user.tz = "Europe/Brussels"
        cls.std_user = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='std_user@test.example.com',
            groups='base.group_user',
            name='Solène StandardUser',
            notification_type='email',
            login='std_user',
            tz='Europe/Brussels'  # UTC + 1 (at least in February)
        )
        cls.portal_user = cls._create_portal_user()

@tagged('appointment_ui', '-at_install', 'post_install')
class AppointmentUITest(AppointmentUICommon):

    @users('apt_manager')
    def test_route_apt_type_search_create_anytime(self):
        self.authenticate(self.env.user.login, self.env.user.login)
        request = self.url_open(
            "/appointment/appointment_type/search_create_anytime",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        ).json()
        result = request.get('result', {})
        appointment_type_id = result.get('appointment_type', {}).get('id')
        self.assertTrue(appointment_type_id, 'The request returns the id of the custom appointment type')
        appointment_type = self.env['appointment.type'].browse(appointment_type_id)
        self.assertEqual(appointment_type.category, 'anytime')
        self.assertEqual(len(appointment_type.slot_ids), 7, "7 slots have been created: (1 / days for 7 days)")
        self.assertTrue(all(slot.slot_type == 'recurring' for slot in appointment_type.slot_ids), "All slots are 'recurring'")

    @users('apt_manager')
    def test_route_apt_type_search_create_anytime_with_context(self):
        self.authenticate(self.env.user.login, self.env.user.login)
        request = self.url_open(
            "/appointment/appointment_type/search_create_anytime",
            data=json.dumps({
                'params': {
                    'context': {
                        'default_is_auto_assign': True,
                    },
                }
            }),
            headers={"Content-Type": "application/json"},
        ).json()
        result = request.get('result', dict())
        appointment_type_id = result.get('appointment_type', {}).get('id')
        self.assertTrue(appointment_type_id, 'The request returns the id of the custom appointment type')

        appointment_type = self.env['appointment.type'].browse(appointment_type_id)
        # All default context fields should be ignored because of clean_context()
        self.assertFalse(appointment_type.is_auto_assign)

    def test_share_appointment_type(self):
        self._create_invite_test_data()
        self.authenticate(None, None)
        res = self.url_open(self.invite_apt_type_bxls_2days.book_url)
        self.assertEqual(res.status_code, 200, "Response should = OK")

    def test_share_appointment_type_multi(self):
        self._create_invite_test_data()
        self.authenticate(None, None)
        res = self.url_open(self.invite_all_apts.book_url)
        self.assertEqual(res.status_code, 200, "Response should = OK")

    @users('apt_manager')
    @freeze_time('2022-02-15T14:00:00')
    def test_action_calendar_meetings_initial_date(self):
        """The bookings calendar opens on the first booking after the current time."""
        appointment_type = self.env['appointment.type'].create({
            'name': 'Type Test Initial Date',
            'schedule_based_on': 'resources',
            'resource_ids': [Command.create({'name': 'Test Resource', 'capacity': 1})],
        })
        self.env['calendar.event'].create([{
            'name': f'Appointment {start:%Y-%m-%d}',
            'appointment_type_id': appointment_type.id,
            'start': start,
            'stop': start + timedelta(hours=1),
        } for start in [datetime(2023, 3, 1), datetime(2022, 1, 1), datetime(2022, 2, 20), datetime(2022, 3, 1)]])

        action = appointment_type.action_calendar_meetings()
        self.assertEqual(action['context']['initial_date'], datetime(2022, 2, 20))

    @users('apt_manager')
    def test_appointment_meeting_url_and_location(self):
        """ Test that booking an appointment creates a calendar event with the correct meeting URL and location. """
        CalendarEvent = self.env['calendar.event']
        self.authenticate(self.env.user.login, self.env.user.login)
        datetime_format = "%Y-%m-%d %H:%M:%S"
        discuss_route = CalendarEvent.DISCUSS_ROUTE

        appointment_with_discuss_videocall_source = self.env['appointment.type'].create({
            'name': 'Schedule a Demo with Odoo Discuss URL',
            'staff_user_ids': self.staff_user_bxls,
            'event_videocall_source': 'discuss',
        })
        appointment_without_videocall_source = self.env['appointment.type'].create({
            'name': 'Schedule a Demo without meeting URL',
            'staff_user_ids': self.staff_user_bxls,
            'event_videocall_source': False,
        })
        phone_question = appointment_with_discuss_videocall_source._get_main_phone_question()
        self.assertTrue(phone_question)
        self.assertEqual(phone_question, appointment_without_videocall_source._get_main_phone_question())

        online_meeting = {
            'allday': 0,
            'duration_str': '1.0',
            'datetime_str': '2022-07-04 12:30:00',
            'staff_user_id': self.staff_user_bxls.id,
            'name': 'Online Meeting',
            f'question_{phone_question.id}': '2025550999',
            'email': 'test1@test.example.com',
            'csrf_token': self.csrf_token()
        }
        meeting_with_location = {
            'allday': 0,
            'duration_str': '1.0',
            'datetime_str': '2022-07-05 10:30:00',
            'staff_user_id': self.staff_user_bxls.id,
            'name': 'Meeting with location',
            f'question_{phone_question.id}': '2025550888',
            'email': 'test2@test.example.com',
            'csrf_token': self.csrf_token(),
        }

        cases = [
            (appointment_with_discuss_videocall_source, online_meeting, True),
            (appointment_without_videocall_source, online_meeting, False),
            (appointment_with_discuss_videocall_source, meeting_with_location, True),
            (appointment_without_videocall_source, meeting_with_location, False),
        ]

        for appointment, appointment_data, expect_discuss in cases:
            # Prevent booking the same slot
            appt_datetime = datetime.strptime(appointment_data.get('datetime_str'), datetime_format)
            new_appt_datetime = appt_datetime.replace(tzinfo=ZoneInfo(appointment.appointment_tz)) + timedelta(hours=1)
            appointment_data.update({'datetime_str': new_appt_datetime.strftime(datetime_format)})

            if appointment_data.get('name') == 'Meeting with location':
                appointment.update({'location_id': self.staff_user_bxls.partner_id.id})
            url = f"/appointment/{appointment.id}/submit"
            res = self.url_open(url, data=appointment_data)
            self.assertEqual(res.status_code, 200, "Response should = OK")
            event = CalendarEvent.search([('appointment_type_id', '=', appointment.id), ('start', '=', new_appt_datetime.astimezone(UTC).replace(tzinfo=None))])
            self.assertIn(event.access_token, res.url)
            with self.subTest(expect_discuss=expect_discuss, access_token=event.access_token):
                if expect_discuss:
                    self.assertIn(discuss_route, event.videocall_location,
                        "Should have discuss link as videocall_location as the appointment type videocall source is set to Odoo Discuss")
                else:
                    self.assertFalse(event.videocall_location,
                        "Should not have a videocall_location as the appointment type doesn't have any videocall source")

                # Ensure the event's location is propagated from the appointment type when its location is set
                self.assertEqual(event.location, appointment.location,
                    "Should have propagated the location from the appointment type.")

    @freeze_time('2022-02-13')
    @users('apt_manager')
    def test_appointment_allday_slot(self):
        self.authenticate(self.env.user.login, self.env.user.login)
        reference_monday = self.reference_monday.replace(hour=0, minute=0, microsecond=0)
        unique_slots = [{
            'allday': True,
            'end_datetime': reference_monday,
            'start_datetime': reference_monday,
        }, {
            'allday': True,
            'end_datetime': reference_monday + timedelta(days=2),
            'start_datetime': reference_monday + timedelta(days=1),
        }]
        apt_type = self.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'category': 'custom',
            'name': 'Custom with allday slots',
            'slot_ids': [(0, 0, {
                'allday': slot['allday'],
                'end_datetime': slot['end_datetime'],
                'slot_type': 'unique',
                'start_datetime': slot['start_datetime'],
            }) for slot in unique_slots],
        })
        phone_question = apt_type._get_main_phone_question()
        appointment_data = {
            "allday": 1,
            "appointment_type_id": apt_type.id,
            "csrf_token": self.csrf_token(),
            "datetime_str": "2022-02-15 00:00:00",
            "duration_str": "48.0",
            "email": "test@test.example.com",
            "name": "Online Meeting",
            f"question_{phone_question.id}": "2025550999",
            "staff_user_id": self.apt_manager.id,
        }

        url = f"/appointment/{apt_type.id}/submit"
        res = self.url_open(url, data=appointment_data)
        self.assertEqual(res.status_code, 200, "Response should = OK")

        meeting = self.env["calendar.event"].search([("appointment_type_id", "=", apt_type.id)])
        self.assertTrue(meeting)
        self.assertTrue(meeting.allday)
        self.assertEqual(meeting.start_date, unique_slots[1]['start_datetime'].date())
        self.assertEqual(meeting.stop_date, unique_slots[1]['end_datetime'].date())

    @freeze_time('2022-02-13')
    @users('apt_manager')
    def test_appointment_crossing_manual_confirmation_treshold(self):
        """ Test that when crossing over the manual confirmation treshold, the attendees are not confirmed """
        self.assertFalse(self.apt_type_resource.meeting_ids)  # Assert initial data
        self.authenticate(self.env.user.login, self.env.user.login)
        resource = self.env['appointment.resource'].sudo().create([{
            "appointment_type_ids": self.apt_type_resource.ids,
            "capacity": 4,
            "name": "Resource",
        }])

        phone_question = self.apt_type_resource._get_main_phone_question()
        self.assertTrue(phone_question)
        self.assertTrue(self.apt_type_resource.auto_confirm)
        self.apt_type_resource.sudo().manual_confirmation_percentage = 0.5  # Set Manual Confirmation at 50%

        appointment_data = {
            "allday": 0,
            "asked_capacity": 4,
            "available_resource_ids": [resource.id],
            "csrf_token": self.csrf_token(),
            "datetime_str": "2022-02-14 15:00:00",
            "duration_str": "1.0",
            "email": "test@test.example.com",
            "name": "Online Meeting",
            f"question_{phone_question.id}": "2025550999",
        }

        url = f"/appointment/{self.apt_type_resource.id}/submit"
        res = self.url_open(url, data=appointment_data)
        self.assertEqual(res.status_code, 200, "Response should = OK")

        meeting = self.env["calendar.event"].search([("appointment_type_id", "=", self.apt_type_resource.id)])
        self.assertTrue(meeting)
        self.assertEqual(meeting.appointment_status, "request")
        self.assertEqual(meeting.attendee_ids.state, "accepted",
            "Crossing over the manual confirmation percentage should confirm the attendees immediately.")
        self.assertEqual(meeting.total_capacity_reserved, 4)

    @freeze_time('2022-02-14')
    @mute_logger('odoo.http')
    @users('apt_manager')
    def test_appointment_answer_required_questions(self):
        """ Check that when submitting a form through the controller, the required
        questions have indeed been answered. """
        self.authenticate(self.env.user.login, self.env.user.login)
        self.apt_type_bxls_2days.write({
            'max_bookings': 10,
            'meeting_ids': False,
            'question_ids': False
        })
        event_values = {
            'csrf_token': self.csrf_token(),
            'datetime_str': '2022-02-14 11:00:00',
            'duration_str': '1.0',
            'email': 'test1@test.example.com',
            'name': 'Meeting Test',
            'staff_user_id': self.staff_user_bxls.id,
        }

        answers_vals = [
            {'name': 'answer 0', 'sequence': 0},
            {'name': 'answer 1', 'sequence': 1}
        ]
        questions = self.env['appointment.question'].create([{
            'answer_ids': [Command.create(vals) for vals in answers_vals] if question_type in ['select', 'checkbox'] else False,
            'appointment_type_ids': self.apt_type_bxls_2days.ids,
            'name': f'question {i}',
            'question_type': question_type,
            'question_required': question_required,
            'sequence': i,
        } for i, (question_type, question_required) in enumerate(
            [('phone', False), ('phone', True), ('char', True), ('select', True), ('checkbox', True)]
        )])
        self.assertEqual(len(questions), 5)
        self.assertEqual(len(questions.answer_ids), 4)
        self.assertListEqual(self.apt_type_bxls_2days.question_ids.ids, questions.ids)

        event_answers = {
            f'question_{questions[0].id}': '   ',
            f'question_{questions[1].id}': '01234',
            f'question_{questions[2].id}': 'Hello',
            f'question_{questions[3].id}': str(questions[3].answer_ids[1].id),
            f'question_{questions[4].id}_answer_{questions[4].answer_ids[0].id}': True,
        }

        res = self.url_open(f"/appointment/{self.apt_type_bxls_2days.id}/submit", {**event_values, **event_answers})
        self.assertEqual(res.status_code, 200, "Response should be OK")
        self.assertEqual(len(self.apt_type_bxls_2days.meeting_ids), 1)
        self.assertEqual(len(self.apt_type_bxls_2days.meeting_ids.appointment_answer_input_ids), 4)  # main phone was stripped out

        for question_key in [key for key in event_answers if key != f'question_{questions[0].id}']:
            with self.subTest(missing_mandatory_question_key=question_key):
                event_answers_copy = event_answers.copy()
                event_answers_copy.pop(question_key)
                res = self.url_open(f"/appointment/{self.apt_type_bxls_2days.id}/submit", {**event_values, **event_answers_copy})
                self.assertEqual(res.status_code, 422)

    @freeze_time('2022-02-14')
    @users('apt_manager')
    def test_appointment_resource_manual_confirmation(self):
        """ Test that when auto_confirm is False, the appointment type is not confirmed
        and the attendees are not confirmed until the booking is confirmed manually.
        """
        self.authenticate(self.env.user.login, self.env.user.login)
        self.assertFalse(self.apt_resource_multiple_bookings.meeting_ids)
        phone_question = self.apt_resource_multiple_bookings._get_main_phone_question()
        self.assertTrue(phone_question)
        resource = self.env['appointment.resource'].sudo().create([{
            'appointment_type_ids': self.apt_resource_multiple_bookings.ids,
            'capacity': 4,
            'name': 'Resource',
        }])

        self.assertTrue(self.apt_resource_multiple_bookings.auto_confirm)
        self.assertEqual(float_compare(self.apt_resource_multiple_bookings.manual_confirmation_percentage, 1.0, 3), 0)
        appointment_data = {
            'available_resource_ids': [resource.id],
            'csrf_token': self.csrf_token(),
            'datetime_str': '2022-02-14 15:00:00',
            'duration_str': '1.0',
            'email': 'test@test.example.com',
            'name': 'Online Meeting',
            'phone': '2025550999',
            f'question_{phone_question.id}': '2025550999',
        }

        url = f'/appointment/{self.apt_resource_multiple_bookings.id}/submit'
        res = self.url_open(url, data=appointment_data)
        self.assertEqual(res.status_code, 200, 'Response should = OK')
        self.assertEqual(len(self.apt_resource_multiple_bookings.meeting_ids), 1)
        self.assertFalse(self.apt_resource_multiple_bookings.meeting_ids[0].user_id)
        self.assertEqual(self.apt_resource_multiple_bookings.meeting_ids[0].appointment_status, 'booked')

        self.apt_resource_multiple_bookings.write({'auto_confirm': False})
        appointment_data['datetime_str'] = '2022-02-14 16:00:00'
        res = self.url_open(url, data=appointment_data)
        self.assertEqual(res.status_code, 200, 'Response should = OK')
        self.assertEqual(len(self.apt_resource_multiple_bookings.meeting_ids), 2)
        self.assertFalse(self.apt_resource_multiple_bookings.meeting_ids[0].user_id)
        self.assertEqual(
            self.apt_resource_multiple_bookings.meeting_ids[0].appointment_status, 'request',
            'When manual confirmation is set, the booking status should be set to request.'
        )

    @freeze_time('2022-02-14')
    @users('apt_manager')
    def test_appointment_staff_user_manual_confirmation(self):
        """ Check that appointment and attendee status are correctly
        set based on the auto_confirm and manual_confirmation_percentage fields"""
        self.authenticate(self.env.user.login, self.env.user.login)
        phone_question = self.apt_type_bxls_2days._get_main_phone_question()
        self.assertTrue(phone_question)
        event_values = {
            'allday': 0,
            'csrf_token': self.csrf_token(),
            'datetime_str': '2022-02-14 11:00:00',
            'duration_str': '1.0',
            'email': 'test1@test.example.com',
            'name': 'Meeting Test',
            f'question_{phone_question.id}': '2025550999',
            'staff_user_id': self.staff_user_bxls.id,
        }
        self.apt_type_bxls_2days.max_bookings = 3
        self.assertTrue(self.apt_type_bxls_2days.auto_confirm)
        self.assertEqual(float_compare(self.apt_type_bxls_2days.manual_confirmation_percentage, 1.0, 3), 0)
        self.assertTrue(self.apt_type_bxls_2days.is_always_confirm)

        res = self.url_open(f"/appointment/{self.apt_type_bxls_2days.id}/submit", event_values)
        self.assertEqual(res.status_code, 200, "Response should be OK")
        first_meeting = self.apt_type_bxls_2days.meeting_ids
        self.assertEqual(len(first_meeting), 1)
        self.assertEqual(first_meeting.appointment_status, "booked")
        self.assertTrue(all(attendee.state == 'accepted' for attendee in first_meeting.attendee_ids))

        self.apt_type_bxls_2days.manual_confirmation_percentage = 0.5
        self.assertFalse(self.apt_type_bxls_2days.is_always_confirm)
        res = self.url_open(f"/appointment/{self.apt_type_bxls_2days.id}/submit", event_values)
        self.assertEqual(res.status_code, 200, "Response should be OK")
        second_meeting = self.apt_type_bxls_2days.meeting_ids - first_meeting
        self.assertEqual(len(second_meeting), 1)
        self.assertEqual(second_meeting.appointment_status, "request")
        self.assertTrue(all(attendee.state == 'accepted' for attendee in second_meeting.attendee_ids))

        # Despite 100% manual_confirmation_percentage, should be 'request' as auto_confirm is False
        self.apt_type_bxls_2days.write({
            'auto_confirm': False,
            'manual_confirmation_percentage': 1.0
        })
        self.assertFalse(self.apt_type_bxls_2days.is_always_confirm)
        res = self.url_open(f"/appointment/{self.apt_type_bxls_2days.id}/submit", event_values)
        self.assertEqual(res.status_code, 200, "Response should be OK")
        third_meeting = self.apt_type_bxls_2days.meeting_ids - (first_meeting | second_meeting)
        self.assertEqual(len(third_meeting), 1)
        self.assertEqual(third_meeting.appointment_status, "request")
        self.assertTrue(all(attendee.state == 'accepted' for attendee in third_meeting.attendee_ids))

    @freeze_time('2022-02-14')
    @users('apt_manager')
    def test_appointment_staff_user_manual_confirmation_percentage(self):
        """ Check that appointment and attendee status are correctly set based on the auto_confirm
        and manual_confirmation_percentage fields when enabled, when booking (multiple) users and
        managing capacity """
        self.authenticate(self.env.user.login, self.env.user.login)
        # 2 users, 3 capacity -> 6 total.
        self.apt_type_manage_capacity_users.write({
            'auto_confirm': True,
            'manual_confirmation_percentage': 0.5,
            'user_capacity': 3,
        })
        self.apt_type_manage_capacity_users.staff_user_ids = [Command.set([self.staff_user_aust.id, self.staff_user_bxls.id])]
        phone_question = self.apt_type_manage_capacity_users._get_main_phone_question()
        self.assertTrue(phone_question)

        event_values = {
            'csrf_token': self.csrf_token(),
            'datetime_str': '2022-02-14 11:00:00',
            'duration_str': '1.0',
            'email': 'test1@test.example.com',
            'name': 'Meeting Test',
            f'question_{phone_question.id}': '2025550999',
            'staff_user_id': self.staff_user_bxls.id,
            'asked_capacity': 3,
        }

        # Booking for 3 capacity with one staff user. Total used is 3/6. It should create a 'booked' event as <= 50%
        res = self.url_open(f"/appointment/{self.apt_type_manage_capacity_users.id}/submit", event_values)
        self.assertEqual(res.status_code, 200, "Response should be OK")
        first_meeting = self.apt_type_manage_capacity_users.meeting_ids
        self.assertEqual(len(first_meeting), 1)
        self.assertEqual(first_meeting.appointment_status, "booked")
        self.assertTrue(all(attendee.state == 'accepted' for attendee in first_meeting.attendee_ids))

        # Booking for 1 capacity with another staff user. Total used is 4/6. It should create a 'request' event as > 50%
        event_values.update({
            'asked_capacity': 1,
            'staff_user_id': self.staff_user_aust.id,
        })
        res = self.url_open(f"/appointment/{self.apt_type_manage_capacity_users.id}/submit", event_values)
        self.assertEqual(res.status_code, 200, "Response should be OK")
        second_meeting = self.apt_type_manage_capacity_users.meeting_ids - first_meeting
        self.assertEqual(len(second_meeting), 1)
        self.assertEqual(second_meeting.appointment_status, "request")
        self.assertTrue(all(attendee.state == 'accepted' for attendee in second_meeting.attendee_ids))

    @users('apt_manager')
    def test_resources_shareable_linked_no_overbooking_with_capacity(self):
        """ Ensure linked shareable resources are correctly handled when managed in gantt view """
        self.authenticate(self.env.user.login, self.env.user.login)
        resource_1, resource_2 = self.env['appointment.resource'].create([{
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 3,
            'name': 'Resource 1',
            'shareable': True,
        }, {
            'appointment_type_ids': self.apt_type_resource.ids,
            'capacity': 4,
            'name': 'Resource 2',
            'shareable': True,
        }])
        resource_1.linked_resource_ids = resource_2
        start = datetime(2022, 2, 14, 15, 0, 0)
        end = start + timedelta(hours=1)

        # Create two bookings to overbook resource 1
        bookings = self.env['calendar.event'].create({
            'appointment_type_id': self.apt_type_resource.id,
            'booking_line_ids': [
                (0, 0, {'appointment_resource_id': resource_1.id, 'capacity_reserved': 2}),
                (0, 0, {'appointment_resource_id': resource_1.id, 'capacity_reserved': 2}),
            ],
            'name': 'Booking',
            'start': start,
            'stop': end,
        })

        # Check that resource 1 was overbooked
        self.assertEqual(len(bookings.resource_ids), 1)
        self.assertEqual(bookings.appointment_resource_ids, resource_1)
        self.assertEqual(bookings.total_capacity_reserved, 4)

        # Resource 1 is fully used, so only resource 2 should be available for another booking
        with freeze_time(self.reference_now):
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=1)
            resource_slots_c5 = self._filter_appointment_slots(slots)
            slots = self.apt_type_resource._get_appointment_slots('UTC', asked_capacity=5)
            resource_slots_c9 = self._filter_appointment_slots(slots)
        available_resources_c5 = [resource['id'] for resource in resource_slots_c5[0]['available_resources']]
        self.assertListEqual(available_resources_c5, resource_2.ids, "Should not allow new booking for the first resource")
        self.assertFalse(resource_slots_c9, "Should not allow overbooking")

        # Appointment created from the website should not fail _check_capacity_reserved
        phone_question = self.apt_type_resource._get_main_phone_question()
        appointment_data = {
            "asked_capacity": 1,
            "available_resource_ids": [resource_2.id],
            "csrf_token": self.csrf_token(),
            "datetime_str": str(start),
            "duration_str": "1.0",
            "email": "test@test.example.com",
            "name": "Online Meeting",
            f"question_{phone_question.id}": "1234567",
        }
        url = f"/appointment/{self.apt_type_resource.id}/submit"
        res = self.url_open(url, data=appointment_data)
        self.assertEqual(res.status_code, 200, "Response should = OK")


@tagged('appointment_ui', '-at_install', 'post_install')
class CalendarTest(AppointmentUICommon):

    def test_meeting_accept_authenticated(self):
        event = self.env["calendar.event"].create(
            {"name": "Doom's day",
             "start": datetime(2019, 10, 25, 8, 0),
             "stop": datetime(2019, 10, 27, 18, 0),
             "partner_ids": [(4, self.std_user.partner_id.id)],
            }
        )
        token = event.attendee_ids[0].access_token
        url = "/calendar/meeting/accept?token=%s&id=%d" % (token, event.id)
        self.authenticate(self.std_user.login, self.std_user.login)
        res = self.url_open(url, method='POST', data={'csrf_token': self.csrf_token()})

        self.assertEqual(res.status_code, 200, "Response should = OK")
        event.attendee_ids[0].invalidate_recordset()
        self.assertEqual(event.attendee_ids[0].state, "accepted", "Attendee should have accepted")

    def test_meeting_accept_unauthenticated(self):
        event = self.env["calendar.event"].create(
            {"name": "Doom's day",
             "start": datetime(2019, 10, 25, 8, 0),
             "stop": datetime(2019, 10, 27, 18, 0),
             "partner_ids": [(4, self.std_user.partner_id.id)],
            }
        )
        token = event.attendee_ids[0].access_token
        url = "/calendar/meeting/accept?token=%s&id=%d" % (token, event.id)
        self.authenticate(None, None)
        res = self.url_open(url, method='POST', data={'csrf_token': self.csrf_token()})

        self.assertEqual(res.status_code, 200, "Response should = OK")
        event.attendee_ids[0].invalidate_recordset()
        self.assertEqual(event.attendee_ids[0].state, "accepted", "Attendee should have accepted")

    @freeze_time('2023, 11, 22')
    def test_meeting_booker_cancel(self):
        """ Test that when appointment Booker cancels the meeting then the event should
        be archived.
        """
        self.authenticate(self.portal_user.login, self.portal_user.login)
        self.apt_type_bxls_2days.write({'is_published': True})
        event = self.env['calendar.event'].create({
            'name': 'Test-Meeting 2',
            'user_id': self.portal_user.id,
            'appointment_booker_id': self.portal_user.partner_id.id,
            'start': datetime(2023, 11, 23, 9, 0),
            'stop':  datetime(2023, 11, 23, 10, 0),
            'partner_ids': [
                (4, self.staff_user_nz.partner_id.id),
                (4, self.staff_user_aust.partner_id.id),
                (4, self.apt_manager.partner_id.id),
                (4, self.portal_user.partner_id.id),
            ],
            'appointment_type_id': self.apt_type_bxls_2days.id,
        })
        cancel_meeting_data = {
            'access_token': event.access_token,
            'partner_id': self.portal_user.partner_id.id,
            'csrf_token': self.csrf_token(),
        }
        cancel_meeting_url = f"/calendar/{event.access_token}/cancel"
        res = self.url_open(cancel_meeting_url, data=cancel_meeting_data)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(event.active)

    @freeze_time('2023, 11, 22')
    def test_meeting_cancel_no_partner(self):
        """ Test cancellation of meeting with no partner. """
        self.authenticate(None, None)
        self.apt_type_bxls_2days.write({'is_published': True})
        event = self.env['calendar.event'].create({
            'name': 'Test-Meeting 1',
            'user_id': self.staff_user_aust.id,
            'appointment_booker_id': self.staff_user_nz.partner_id.id,
            'start': datetime(2023, 11, 23, 8, 0),
            'stop':  datetime(2023, 11, 23, 9, 0),
            'partner_ids':  [
                (4, self.staff_user_nz.partner_id.id),
                (4, self.portal_user.partner_id.id),
                (4, self.staff_user_aust.partner_id.id),
            ],
            'appointment_type_id': self.apt_type_bxls_2days.id,
        })
        cancel_meeting_data = {
            'access_token': event.access_token,
            'csrf_token': self.csrf_token(),
        }
        cancel_meeting_url = f"/calendar/{event.access_token}/cancel"
        res = self.url_open(cancel_meeting_url, data=cancel_meeting_data)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(event.active)
