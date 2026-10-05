# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import Form, freeze_time

from .common import TestPlanningFieldServiceCommon


@freeze_time('2026-01-06 00:00:00')
class TestPlanningFieldServiceFlow(TestPlanningFieldServiceCommon):
    def test_state_changes(self):
        self.assertEqual(self.intervention.state, '2_published')
        self.intervention.action_sign_in()
        self.assertEqual(self.intervention.state, '3_in_progress')
        self.intervention.action_complete()
        self.assertEqual(self.intervention.state, '4_completed', 'task state should change to done')

    def test_navigation_link(self):
        partner = self.env['res.partner'].create({
            'name': 'A Test Partner',
            'street': 'Chaussée de Namur 40',
            'zip': '1367',
            'city': 'Ramillies',
        })
        self.assertEqual(
            partner.action_partner_navigate()['url'],
            "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e+de+Namur+40%2C+Ramillies+1367",
        )

    def test_planning_user_slot_creation_without_access_error_updates_partner_phone(self):
        """
        Verify that creating a planning slot with a customer as planning user
        does not raise AccessError and correctly updates the partner phone.
        """
        self.george_user.group_ids = [Command.link(self.env.ref('base.group_partner_manager').id)]
        self.assertFalse(self.planning_manager.partner_id.phone)

        slot = self.env['planning.slot'].create({
            'resource_ids': self.george_employee.resource_id.ids,
            'state': '2_published',
        })

        slot.with_user(self.george_user).write({'partner_id': self.planning_manager.partner_id.id, 'partner_phone': '9016755950'})

        self.assertTrue(slot.partner_id, "Customer should be set when creating a slot with a partner.")
        self.assertEqual(self.planning_manager.partner_id.phone, '9016755950', "Partner phone number should be updated according to the partner_phone field.")

    def test_planning_slot_action_sign_in_without_end_datetime(self):
        slot = self.intervention
        slot.end_datetime = False
        slot.action_sign_in()

        self.assertEqual(slot.start_datetime, fields.Datetime.now())
        self.assertEqual(slot.end_datetime, fields.Datetime.now() + relativedelta(hours=1))
        self.assertEqual(slot.state, '3_in_progress')

    def test_action_sign_in_assigns_current_user_resource_when_no_employee_assigned(self):
        # action_self_assign() (called by action_sign_in() below) requires the
        # acting user to have an employee of their own, which planning_manager
        # doesn't have by default.
        manager_employee = self.env['hr.employee'].create({
            'name': 'Planning Manager',
            'user_id': self.planning_manager.id,
        })
        slot = self.second_intervention
        self.assertFalse(slot.employee_public_ids)

        slot.with_user(self.planning_manager).action_sign_in()

        self.assertEqual(slot.resource_ids, manager_employee.resource_id)
        self.assertEqual(slot.state, '3_in_progress')

    def test_action_sign_in_keeps_existing_resource_when_employee_already_assigned(self):
        slot = self.intervention
        self.assertTrue(slot.employee_public_ids)
        self.assertEqual(slot.resource_ids, self.george_employee.resource_id)

        slot.with_user(self.planning_manager).action_sign_in()

        self.assertEqual(slot.resource_ids, self.george_employee.resource_id)
        self.assertEqual(slot.state, '3_in_progress')

    def test_action_sign_in_assigns_related_material_resources(self):
        """ Signing in on an unassigned slot should also pull in any material
        resource assigned to the signing-in user's employee (e.g. their van,
        tools, ...), the same way action_self_assign() does when used
        directly on an open shift. """
        manager_employee = self.env['hr.employee'].create({
            'name': 'Planning Manager',
            'user_id': self.planning_manager.id,
        })
        drill = self.env['resource.resource'].create({
            'name': 'Drill',
            'resource_type': 'material',
            'assigned_employee_id': manager_employee.id,
        })
        slot = self.second_intervention
        self.assertFalse(slot.employee_public_ids)

        slot.with_user(self.planning_manager).action_sign_in()

        self.assertEqual(slot.resource_ids, manager_employee.resource_id + drill)
        self.assertEqual(slot.state, '3_in_progress')

    def test_onchange_break_time(self):
        open_shift = self.env['planning.slot'].create({
            'name': 'Open shift',
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
            'state': '2_published',
        })
        for slot in [open_shift, self.intervention]:
            self.assertEqual(slot.allocated_hours, 4)
            self.assertEqual(slot.allocated_percentage, 100)
            self.assertEqual(slot.break_time, 0)
            with Form(slot) as intervention_form:
                intervention_form.break_time = 1
                self.assertEqual(intervention_form.allocated_hours, 3)
                self.assertEqual(intervention_form.break_time, 1)
                intervention_form.break_time = 2
                self.assertEqual(intervention_form.allocated_hours, 2)
                self.assertEqual(intervention_form.break_time, 2)
                intervention_form.break_time = 3
                self.assertEqual(intervention_form.allocated_hours, 1)
                self.assertEqual(intervention_form.break_time, 3)
                intervention_form.break_time = 4
                self.assertEqual(intervention_form.allocated_hours, 0)
                self.assertEqual(intervention_form.break_time, 4)

    def test_onchange_break_time_after_removing_dates(self):
        """ Removing the dates from a shift that has a break time must reset it to 0 """
        open_shift = self.env['planning.slot'].create({
            'name': 'Open shift',
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
            'state': '2_published',
        })

        slot_form = Form(open_shift)

        slot_form.break_time = 1
        self.assertEqual(slot_form.allocated_hours, 3)

        slot_form.end_datetime = False
        slot_form.start_datetime = False

        self.assertEqual(slot_form.break_time, 0, "break time resets to 0 when the shift has no dates")

    def test_planning_slot_onchange_break_time_with_schedule(self):
        self.setUpCalendars()
        self.george_employee.resource_calendar_id = self.company_calendar
        self.george_employee.resource_id.tz = 'UTC'
        slot = self.env['planning.slot'].create({
            'name': 'Open shift',
            'resource_ids': self.george_employee.resource_id.ids,
            'start_datetime': fields.Datetime.to_datetime("2025-01-03 08:00:00"),
            'end_datetime': fields.Datetime.to_datetime("2025-01-03 12:00:00"),
            'state': '2_published',
        })
        self.assertEqual(slot.allocated_hours, 4)
        self.assertEqual(slot.allocated_percentage, 100)
        self.assertEqual(slot.break_time, 0)
        with Form(slot) as intervention_form:
            intervention_form.start_datetime = fields.Datetime.to_datetime("2025-01-03 07:00:00")
            self.assertEqual(intervention_form.allocated_hours, 4)
            self.assertEqual(intervention_form.break_time, 1)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.start_datetime = fields.Datetime.to_datetime("2025-01-03 08:00:00")
            self.assertEqual(intervention_form.allocated_hours, 4)
            self.assertEqual(intervention_form.break_time, 0)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.start_datetime = fields.Datetime.to_datetime("2025-01-03 06:00:00")
            self.assertEqual(intervention_form.allocated_hours, 4)
            self.assertEqual(intervention_form.break_time, 2)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.break_time = 3
            self.assertEqual(intervention_form.allocated_hours, 3)
            self.assertEqual(intervention_form.break_time, 3)
            self.assertEqual(intervention_form.allocated_percentage, 75)
            intervention_form.start_datetime = fields.Datetime.to_datetime("2025-01-03 07:00:00")
            self.assertEqual(intervention_form.allocated_hours, 3)
            self.assertEqual(intervention_form.break_time, 2)
            self.assertEqual(intervention_form.allocated_percentage, 75)
            intervention_form.break_time = 3
            self.assertEqual(intervention_form.allocated_hours, 2)
            self.assertEqual(intervention_form.break_time, 3)
            self.assertEqual(intervention_form.allocated_percentage, 50)
            intervention_form.start_datetime = fields.Datetime.to_datetime("2025-01-03 08:00:00")
            self.assertEqual(intervention_form.allocated_hours, 2)
            self.assertEqual(intervention_form.break_time, 2)
            self.assertEqual(intervention_form.allocated_percentage, 50)
            intervention_form.allocated_hours = 4
            self.assertEqual(intervention_form.allocated_hours, 4)
            self.assertEqual(intervention_form.break_time, 0)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.save()

    def test_planning_slot_onchange_negative_break_time(self):
        self.assertEqual(self.intervention.allocated_hours, 4)
        self.assertEqual(self.intervention.allocated_percentage, 100)
        self.assertEqual(self.intervention.break_time, 0)
        with Form(self.intervention) as intervention_form:
            intervention_form.break_time = 5
            self.assertEqual(intervention_form.allocated_hours, 0)
            self.assertEqual(intervention_form.break_time, 5)
            intervention_form.break_time = -1
            self.assertEqual(intervention_form.allocated_hours, 0)
            self.assertEqual(intervention_form.break_time, 0)

    def test_auto_plan_field_service_shifts(self):
        self.env.user.company_id.resource_calendar_id = self.env['resource.calendar'].create({
            'name': '8/16 Company Calendar',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 8, 'hour_to': 16})
                for day in range(7)
            ],
        })

        role = self.env['planning.role'].create({'name': "Role"})
        self.env['resource.resource'].create([{
            'name': "Resource 1",
            'default_role_id': role.id,
        }])

        # Day 1: priority ordering
        #     - One urgent shift spans the full day (8h)
        #     - Three lower-priority shifts on the same day: they should be skipped
        #       because the resource is already assigned to the urgent one.
        day1_low, day1_mid, day1_high, day1_urgent = self.env['planning.slot'].create([{
            'name': 'Day1 Low',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime':   datetime(2023, 7, 28, 16, 0),
            'role_id': role.id,
            'allocated_hours': 6,
            'priority': '0',
        }, {
            'name': 'Day1 Mid',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime':   datetime(2023, 7, 28, 16, 0),
            'role_id': role.id,
            'allocated_hours': 6,
            'priority': '1',
        }, {
            'name': 'Day1 High',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime':   datetime(2023, 7, 28, 16, 0),
            'role_id': role.id,
            'allocated_hours': 6,
            'priority': '2',
        }, {
            'name': 'Day1 Urgent',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime':   datetime(2023, 7, 28, 16, 0),
            'role_id': role.id,
            'allocated_hours': 6,
            'priority': '3',
        }])

        # Day 2: same-priority falls back to chronological order
        #     - Both shifts have equal priority; the one created first should be
        #       planned first.
        day2_first, day2_second = self.env['planning.slot'].create([{
            'name': 'Day2 First',
            'start_datetime': datetime(2023, 7, 29, 8),
            'end_datetime':   datetime(2023, 7, 29, 16, 0),
            'role_id': role.id,
            'allocated_hours': 5,
            'priority': '1',
        }, {
            'name': 'Day2 Second',
            'start_datetime': datetime(2023, 7, 29, 10),
            'end_datetime':   datetime(2023, 7, 29, 16, 0),
            'role_id': role.id,
            'allocated_hours': 5,
            'priority': '1',
        }])

        # Day 3: independent day, single shift
        #     - Confirms that a day with no resource contention is still handled
        #       correctly after the priority logic on earlier days.
        day3 = self.env['planning.slot'].create({
            'name': 'Day3 Only',
            'start_datetime': datetime(2023, 7, 31, 8),
            'end_datetime':   datetime(2023, 7, 31, 12, 0),
            'role_id': role.id,
            'allocated_hours': 4,
            'priority': '0',
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-02 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-02 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])
        planned_shifts = res['open_shift_assigned']

        # Day 1: only the urgent shift is assigned; high, mid and low are skipped
        self.assertIn(day1_urgent.id, planned_shifts, "Only the urgent shift should be planned")
        self.assertNotIn(day1_high.id, planned_shifts, "The lower priority shifts should not be planned (resource consumed)")
        self.assertNotIn(day1_mid.id, planned_shifts, "The lower priority shifts should not be planned (resource consumed)")
        self.assertNotIn(day1_low.id, planned_shifts, "The lower priority shifts should not be planned (resource consumed)")

        # Day 2: same priority → first-created shift wins, second is skipped
        self.assertIn(day2_first.id, planned_shifts, "The first shift should be planned")
        self.assertNotIn(day2_second.id, planned_shifts, "The second shift should not be planned (resource consumed)")

        # Day 3: uncontested shift is always assigned
        self.assertIn(day3.id, planned_shifts, "Day-3 shift should always be assigned since it is the only shift of the day")

    def test_get_gantt_data(self):
        slot = self.env['planning.slot'].create({
            'name': "Test slot",
            'resource_ids': self.henri_employee.resource_id.ids,
            'partner_id': self.partner.id,
            'start_datetime': fields.Datetime.now().replace(hour=10, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=15, minute=0, second=0),
        })

        gantt_data = self.env['planning.slot'].with_user(self.george_user).get_gantt_data(
            domain=[["id", "in", slot.ids]],
            groupby=['resource_ids'],
            read_specification={'display_name': {}, 'resource_ids': {}, 'partner_id': {}},
            start_date=fields.Datetime.now().replace(hour=0, minute=0, second=0),
            stop_date=fields.Datetime.now().replace(hour=23, minute=59, second=59),
            scale="day",
        )
        self.assertNotIn('resource_work_locations', gantt_data, "There should not be work locations since user is not manager")

        gantt_data = self.env['planning.slot'].get_gantt_data(
            domain=[["id", "in", slot.ids]],
            groupby=['resource_ids'],
            read_specification={'display_name': {}, 'resource_ids': {}, 'partner_id': {}},
            start_date=fields.Datetime.now().replace(hour=0, minute=0, second=0),
            stop_date=fields.Datetime.now().replace(hour=23, minute=59, second=59),
            scale="week",
        )
        self.assertNotIn('resource_work_locations', gantt_data, "There should not be work locations if scale is not by day")

        gantt_data = self.env['planning.slot'].get_gantt_data(
            domain=[["id", "in", slot.ids]],
            groupby=['resource_ids'],
            read_specification={'display_name': {}, 'resource_ids': {}, 'partner_id': {}},
            start_date=fields.Datetime.now().replace(hour=0, minute=0, second=0),
            stop_date=fields.Datetime.now().replace(hour=23, minute=59, second=59),
            scale="day",
        )
        self.assertIn('resource_work_locations', gantt_data, "There should be work locations in the data")
        self.assertIn(self.henri_employee.resource_id.id, gantt_data['resource_work_locations'], "Henri's work location should be in the data")
        self.assertEqual({'contact_address_complete', 'partner_latitude', 'partner_longitude'}, gantt_data['resource_work_locations'][self.henri_employee.resource_id.id].keys())

    def test_travel_time_information_correctly_reset(self):
        slot = self.env['planning.slot'].create({
            'name': "Test slot",
            'resource_ids': self.henri_employee.resource_id.ids,
            'partner_id': self.partner.id,
            'start_datetime': fields.Datetime.now().replace(hour=10, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=15, minute=0, second=0),
            'travel_time_in': 0.5,
            'travel_time_out': 0.0,
            'travel_distance_in': 10,
            'travel_distance_out': 5,
        })

        slot_copy = slot.copy()
        self.assertFalse(slot_copy.travel_time_in, "Travel time should not be copied over")
        self.assertFalse(slot_copy.travel_time_out, "Travel time should not be copied over")
        self.assertFalse(slot_copy.travel_distance_in, "Travel distances should not be copied over")
        self.assertFalse(slot_copy.travel_distance_out, "Travel distances should not be copied over")

        slot.write({'resource_ids': self.george_employee.resource_id.ids})
        self.assertFalse(slot_copy.travel_time_in, "Travel time should be reset when switching resources")
        self.assertFalse(slot_copy.travel_time_out, "Travel time should be reset when switching resources")
        self.assertFalse(slot_copy.travel_distance_in, "Travel distances should be reset when switching resources")
        self.assertFalse(slot_copy.travel_distance_out, "Travel distances should be reset when switching resources")

    def test_planning_slot_onchange_resource(self):
        self.george_employee.resource_id.tz = 'UTC'
        self.henri_employee.resource_id.tz = 'UTC'
        george_calendar = self.env['resource.calendar'].create({
            'name': 'Calendar 1',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 16}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 16}),
            ]
        })
        self.george_employee.resource_calendar_id = george_calendar
        henri_calendar = self.env['resource.calendar'].create({
            'name': 'Calendar 2',
            'hours_per_day': 4.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 10, 'hour_to': 14}),
                (0, 0, {'dayofweek': '4', 'hour_from': 10, 'hour_to': 14}),
            ],
        })
        self.henri_employee.resource_calendar_id = henri_calendar

        self.intervention.resource_ids = self.george_employee.resource_id
        self.intervention.start_datetime = fields.Datetime.to_datetime("2026-09-03 08:00:00")
        self.intervention.end_datetime = fields.Datetime.to_datetime("2026-09-04 16:00:00")

        self.assertEqual(self.intervention.allocated_hours, 16)
        self.assertEqual(self.intervention.break_time, 16)
        self.assertEqual(self.intervention.allocated_percentage, 100)

        with Form(self.intervention) as intervention_form:
            # When no resource it uses the company calendar: 8h/day
            intervention_form.resource_ids = self.env['resource.resource']
            self.assertEqual(intervention_form.allocated_hours, 16)
            self.assertEqual(intervention_form.break_time, 0)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.resource_ids = self.henri_employee.resource_id
            self.assertEqual(intervention_form.allocated_hours, 8)
            self.assertEqual(intervention_form.break_time, 24)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.resource_ids = self.george_employee.resource_id + self.henri_employee.resource_id
            self.assertEqual(intervention_form.allocated_hours, 24)
            self.assertEqual(intervention_form.break_time, 0)   # When multiple days + multiple resources, break_time is not displayed
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.end_datetime = fields.Datetime.to_datetime("2026-09-03 16:00:00")
            self.assertEqual(intervention_form.allocated_hours, 12)
            self.assertEqual(intervention_form.break_time, 4)
            self.assertEqual(intervention_form.allocated_percentage, 100)

    def test_planning_slot_allocated_hours_on_multiple_resources(self):
        slot = self.intervention
        with Form(slot) as intervention_form:
            intervention_form.end_datetime = fields.Datetime.to_datetime("2026-01-06 16:00:00")
            self.assertEqual(len(intervention_form.resource_ids), 1)
            self.assertEqual(intervention_form.allocated_hours, 8)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.resource_ids.add(self.henri_employee.resource_id)
            self.assertEqual(len(intervention_form.resource_ids), 2)
            self.assertEqual(intervention_form.allocated_hours, 16)
            self.assertEqual(intervention_form.allocated_percentage, 100)
            intervention_form.resource_ids = self.george_employee.resource_id
            self.assertEqual(len(intervention_form.resource_ids), 1)
            self.assertEqual(intervention_form.allocated_hours, 8)
            self.assertEqual(intervention_form.allocated_percentage, 100)

    def test_message_subtypes_based_on_configuration(self):
        for configuration, expected, unexpected in [
            ("switch", self.env.ref("planning_field_service.mt_replacement_requested"), self.env.ref("planning_field_service.mt_shift_unassigned")),
            ("unassign", self.env.ref("planning_field_service.mt_shift_unassigned"), self.env.ref("planning_field_service.mt_replacement_requested")),
        ]:
            self.env.company.planning_employee_unavailabilities = configuration
            slot = self.env['planning.slot'].with_user(self.planning_manager).create({
                'name': "Test slot",
                'start_datetime': fields.Datetime.now().replace(hour=10, minute=0, second=0),
                'end_datetime': fields.Datetime.now().replace(hour=15, minute=0, second=0),
            })
            self.assertIn(expected, slot.message_follower_ids.subtype_ids, "The %s subtype should be added to the slot's followers" % expected.name)
            self.assertNotIn(unexpected, slot.message_follower_ids.subtype_ids, "The %s subtype should not be added to the slot's followers" % unexpected.name)

    def test_publish_shift_subscribes_assigned_employee(self):
        slot = self.env["planning.slot"].create({
            "name": "Test slot",
            "resource_ids": self.henri_employee.resource_id.ids,
            "start_datetime": fields.Datetime.now().replace(hour=10, minute=0, second=0),
            "end_datetime": fields.Datetime.now().replace(hour=15, minute=0, second=0),
            "partner_id": self.partner.id,
        })
        slot.action_send()
        self.assertIn(slot.resource_ids.employee_id.work_contact_id, slot.message_follower_ids.partner_id, "The assigned employee should be subscribed as a follower.")
        self.assertIn(
            self.env.ref("planning_field_service.mt_shift_reassigned"),
            slot.message_follower_ids.subtype_ids,
            "The 'Shift Re-assigned' subtype is missing from the assigned employee follower."
        )
        self.assertIn(
            self.env.ref("planning_field_service.mt_shift_rescheduled"),
            slot.message_follower_ids.subtype_ids,
            "The 'Shift Rescheduled' subtype is missing from the assigned employee follower."
        )

    def _create_slots(self, *resources, **kwargs):
        return self.env['planning.slot'].create([{
            'name': "Test slot",
            'resource_ids': resource.ids,
            'start_datetime': fields.Datetime.now().replace(hour=10, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=15, minute=0, second=0),
            **kwargs,
        } for resource in resources])

    def test_publishing_several_shifts_at_once_subscribes_each_resource_to_its_own_shift(self):
        henri_slot, george_slot = self._create_slots(self.henri_employee.resource_id, self.george_employee.resource_id)
        (henri_slot | george_slot).write({'state': '2_published'})
        self.assertEqual(
            henri_slot.message_follower_ids.partner_id, self.henri_user.partner_id,
            "Publishing several shifts at once should not subscribe the resources of the other shifts.",
        )
        self.assertEqual(
            george_slot.message_follower_ids.partner_id, self.george_user.partner_id,
            "Publishing several shifts at once should not subscribe the resources of the other shifts.",
        )

    def test_draft_shift_written_along_a_published_one_subscribes_nobody(self):
        published, draft = self._create_slots(self.henri_employee.resource_id, self.george_employee.resource_id)
        published.state = '2_published'
        (published | draft).write({'name': "Renamed"})
        self.assertFalse(draft.message_follower_ids, "The resources of a draft shift should not be subscribed to it.")

    def test_resources_are_not_subscribed_to_the_customer_messages(self):
        slot = self._create_slots(self.henri_employee.resource_id, state='2_published')
        follower = slot.message_follower_ids.filtered(lambda follower: follower.partner_id == self.henri_user.partner_id)
        self.assertNotIn(
            self.env.ref('mail.mt_comment'), follower.subtype_ids,
            "The assigned resources should not receive the messages sent to the customer.",
        )

    def test_subtype_selection_of_an_already_subscribed_resource_is_kept(self):
        slot = self._create_slots(self.henri_employee.resource_id, state='2_published')
        follower = slot.message_follower_ids.filtered(lambda follower: follower.partner_id == self.henri_user.partner_id)
        follower.subtype_ids = self.env.ref("planning_field_service.mt_shift_reassigned")
        slot.write({'state': '2_published'})
        self.assertEqual(
            follower.subtype_ids, self.env.ref("planning_field_service.mt_shift_reassigned"),
            "Writing on the shift again should not reset the subtypes the resource chose to follow.",
        )

    def test_unassigning_one_of_several_resources_notifies_the_unassignment(self):
        slot = self._create_slots(
            (self.henri_employee | self.george_employee).resource_id, state='2_published',
        )
        self.env.cr.precommit.run()
        messages = slot.message_ids
        slot.resource_ids = self.henri_employee.resource_id
        self.env.cr.precommit.run()
        self.assertIn(
            self.env.ref("planning_field_service.mt_shift_unassigned"), (slot.message_ids - messages).subtype_id,
            "Removing one of the resources of a shift should notify that it was unassigned.",
        )

    def test_unassignment_is_notified_whatever_the_unavailabilities_configuration(self):
        self.env.company.planning_employee_unavailabilities = 'switch'
        slot = self._create_slots(self.henri_employee.resource_id, state='2_published')
        self.env.cr.precommit.run()
        messages = slot.message_ids
        slot.resource_ids = False
        self.env.cr.precommit.run()
        self.assertIn(
            self.env.ref("planning_field_service.mt_shift_unassigned"), (slot.message_ids - messages).subtype_id,
            "A manager unassigning a resource should notify it even if employees cannot unassign themselves.",
        )
        self.assertIn(
            self.env.ref("planning_field_service.mt_shift_unassigned"), slot._mail_get_message_subtypes(),
            "The 'Shift Unassigned' subtype should stay visible, otherwise it cannot be unfollowed.",
        )
