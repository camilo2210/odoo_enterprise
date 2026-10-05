# Part of Odoo. See LICENSE file for full copyright and licensing details

import re
from datetime import date, datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError

from odoo import Command, fields
from odoo.tests import tagged, Form, new_test_user, freeze_time
from odoo.tests.common import HttpCase

from odoo.addons.mail.tests.common import MockEmail
from .common import TestCommonPlanning


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanning(HttpCase, TestCommonPlanning, MockEmail):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.classPatch(cls.env.cr, 'now', datetime.now)
        with freeze_time('2019-05-01'):
            cls.setUpCalendars()
            cls.setUpEmployees()
        calendar_joseph = cls.env['resource.calendar'].create({
            'name': 'Calendar 1',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 9, 'hour_to': 13}),
                (0, 0, {'dayofweek': '3', 'hour_from': 14, 'hour_to': 18}),
            ]
        })
        calendar_bert = cls.env['resource.calendar'].create({
            'name': 'Calendar 2',
            'hours_per_day': 4,
            'attendance_ids': [
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
            ],
        })
        cls.env.user.company_id.resource_calendar_id = cls.company_calendar
        cls.employee_joseph.resource_calendar_id = calendar_joseph
        cls.employee_bert.resource_calendar_id = calendar_bert
        cls.slot, cls.slot2 = cls.env['planning.slot'].create([
            {
                'start_datetime': datetime(2019, 6, 27, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 27, 18, 0, 0),
            },
            {
                'start_datetime': datetime(2019, 6, 27, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 28, 18, 0, 0),
            }
        ])
        cls.template = cls.env['planning.slot.template'].create({
            'start_time': 11,
            'end_time': 14,
            'duration_days': 1,
        })

        cls.flex_role = cls.env['planning.role'].create({'name': 'flex role'})

        cls.flexible_calendar_40_8, cls.flexible_calendar_50_10, cls.fully_flexible_calendar = cls.env['resource.calendar'].create([
            {
                'name': 'Flexible Calendar 40h/week',
                'calendar_type': 'undefined',
                'attendance_ids': [],
                'hours_per_week': 40,
                'hours_per_day': 8,
            },
            {
                'name': 'Flexible Calendar 50h/week',
                'calendar_type': 'undefined',
                'attendance_ids': [],
                'hours_per_week': 50,
                'hours_per_day': 10,
            },
            {
                'name': 'Fully Flexible Calendar',
                'calendar_type': 'undefined',
                'attendance_ids': [],
            },
        ])
        cls.flex_employee = cls.env['hr.employee'].create({
            'name': 'Night employee',
            'resource_calendar_id': cls.flexible_calendar_40_8.id,
            'default_planning_role_id': cls.flex_role.id,
            'tz': 'UTC',
        })

    def test_allocated_hours_defaults(self):
        self.assertEqual(self.slot.allocated_hours, 8, "It should follow the calendar of the resource to compute the allocated hours.")
        self.assertEqual(self.slot.allocated_percentage, 100, "It should have the default value")

    def test_change_percentage(self):
        self.slot.allocated_percentage = 60
        self.assertEqual(self.slot.allocated_hours, 8 * 0.60, "It should 60%% of working hours")
        self.slot2.allocated_percentage = 60
        self.assertEqual(self.slot2.allocated_hours, 16 * 0.60)

    def test_change_hours_more(self):
        self.slot.allocated_hours = 12
        self.assertEqual(self.slot.allocated_percentage, 150)
        self.slot2.allocated_hours = 24
        self.assertEqual(self.slot2.allocated_percentage, 150)

    def test_change_hours_less(self):
        self.slot.allocated_hours = 4
        self.assertEqual(self.slot.allocated_percentage, 50)
        self.slot2.allocated_hours = 8
        self.assertEqual(self.slot2.allocated_percentage, 50)

    def test_change_start(self):
        self.slot.start_datetime += relativedelta(hours=2)
        self.assertEqual(self.slot.allocated_percentage, 100, "It should still be 100%")
        self.assertEqual(self.slot.allocated_hours, 8, "It should decreased by 2 hours")

    def test_change_start_partial(self):
        self.slot.allocated_percentage = 80
        self.slot.start_datetime += relativedelta(hours=2)
        self.slot.flush_recordset()
        self.slot.invalidate_recordset()
        self.assertEqual(self.slot.allocated_hours, 8 * 0.8, "It should be decreased by 2 hours and percentage applied")
        self.assertEqual(self.slot.allocated_percentage, 80, "It should still be 80%")

    def test_change_end(self):
        self.slot.end_datetime -= relativedelta(hours=2)
        self.assertEqual(self.slot.allocated_percentage, 100, "It should still be 100%")
        self.assertEqual(self.slot.allocated_hours, 8, "It should decreased by 2 hours")

    def test_set_template(self):
        self.env.user.tz = 'Europe/Brussels'
        self.slot.template_id = self.template
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 9, 0), 'It should set time from template, in user timezone (11am CET -> 9am UTC)')

    def test_set_overnight_template(self):
        template = self.env['planning.slot.template'].create({
            'start_time': 23,
            'end_time': 1,
            'duration_days': 2,
        })
        self.employee_joseph.resource_calendar_id = self.company_calendar
        self.slot.resource_ids = self.employee_joseph.resource_id
        self.slot.template_id = template
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 23, 0))
        self.assertEqual(self.slot.end_datetime, datetime(2019, 6, 28, 1, 0))

    def test_change_employee_with_template(self):
        self.env.user.tz = 'UTC'
        self.slot.template_id = self.template
        self.env.flush_all()

        # simulate public user (no tz)
        self.env.user.tz = False
        self.slot.resource_ids = self.employee_janice.resource_id
        self.assertEqual(self.slot.template_id, self.template, 'It should keep the template')
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 15, 0), 'It should adjust for employee timezone: 11am EDT -> 3pm UTC')

    def test_change_employee(self):
        """ Ensures that changing the employee does not have an impact to the shift. """
        self.env.user.tz = 'UTC'
        self.slot.resource_ids = self.employee_joseph.resource_id
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 8, 0), 'It should not adjust to employee calendar')
        self.assertEqual(self.slot.end_datetime, datetime(2019, 6, 27, 18, 0), 'It should not adjust to employee calendar')
        self.slot.resource_ids = self.employee_bert.resource_id
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 8, 0), 'It should not adjust to employee calendar')
        self.assertEqual(self.slot.end_datetime, datetime(2019, 6, 27, 18, 0), 'It should not adjust to employee calendar')

    def test_create_with_employee(self):
        """ This test's objective is to mimic shift creation from the gant view and ensure that the correct behavior is met.
            This test objective is to test the default values when creating a new shift for an employee when provided defaults are within employee's calendar workdays
        """
        self.env.user.tz = 'UTC'
        PlanningSlot = self.env['planning.slot'].with_context(
            tz='UTC',
            default_start_datetime='2019-06-27 00:00:00',
            default_end_datetime='2019-06-27 23:59:59',
            default_resource_ids=self.resource_joseph.ids)
        defaults = PlanningSlot.default_get(['resource_ids', 'start_datetime', 'end_datetime'])
        self.assertEqual(defaults.get('start_datetime'), datetime(2019, 6, 27, 9, 0), 'It should be adjusted to employee calendar: 0am -> 9pm')
        self.assertEqual(defaults.get('end_datetime'), datetime(2019, 6, 27, 18, 0), 'It should be adjusted to employee calendar: 0am -> 18pm')

    def test_specific_time_creation(self):
        self.env.user.tz = 'UTC'
        PlanningSlot = self.env['planning.slot'].with_context(
            tz='UTC',
            default_start_datetime='2020-10-05 06:00:00',
            default_end_datetime='2020-10-05 12:30:00',
            planning_keep_default_datetime=True)
        defaults = PlanningSlot.default_get(['start_datetime', 'end_datetime'])
        self.assertEqual(defaults.get('start_datetime'), datetime(2020, 10, 5, 6, 0), 'start_datetime should not change')
        self.assertEqual(defaults.get('end_datetime'), datetime(2020, 10, 5, 12, 30), 'end_datetime should not change')

    def test_create_with_employee_outside_schedule(self):
        """ This test objective is to test the default values when creating a new shift for an employee when provided defaults are not within employee's calendar workdays """
        self.env.user.tz = 'UTC'
        # Case 1: Create a planning slot on non-working days with a specific employee resource
        PlanningSlot = self.env['planning.slot'].with_context(
            tz='UTC',
            default_start_datetime='2019-06-26 00:00:00',
            default_end_datetime='2019-06-26 23:59:59',
            default_resource_ids=self.resource_joseph.ids)
        defaults = PlanningSlot.default_get(['resource_ids', 'start_datetime', 'end_datetime'])
        self.assertEqual(defaults.get('start_datetime'), datetime(2019, 6, 26, 8, 0), 'It should adjust to employee calendar: 0am -> 8pm')
        self.assertEqual(defaults.get('end_datetime'), datetime(2019, 6, 26, 17, 0), 'It should adjust to employee calendar: 0am -> 5am')

        # Case 2: Create a planning slot on non-working days without a specific employee resource
        PlanningSlot = self.env['planning.slot'].with_context(
            tz='UTC',
            default_start_datetime='2019-12-07 00:00:00',
            default_end_datetime='2019-12-08 23:59:59',
        )
        defaults = PlanningSlot.default_get(['resource_ids', 'start_datetime', 'end_datetime'])

        self.assertEqual(
            defaults.get('start_datetime'),
            datetime(2019, 12, 7, 8, 0),
            'The start time should be adjusted to the default working hours: 8:00 AM on non-working days'
        )
        self.assertEqual(
            defaults.get('end_datetime'),
            datetime(2019, 12, 8, 17, 0),
            'The end date should be adjusted to the default working hours: 17:00 on on non-working days'
        )

    def test_create_without_employee(self):
        """ This test objective is to test the default values when creating a new shift when no employee is set """
        self.env.company.tz = 'UTC'
        self.env.user.tz = 'UTC'
        PlanningSlot = self.env['planning.slot'].with_context(
            tz='UTC',
            default_start_datetime='2019-06-27 00:00:00',
            default_end_datetime='2019-06-27 23:59:59',
            default_resource_ids=False)
        defaults = PlanningSlot.default_get(['resource_ids', 'start_datetime', 'end_datetime'])
        self.assertEqual(defaults.get('start_datetime'), datetime(2019, 6, 27, 6, 0), 'It should adjust to employee calendar: 0am -> 6pm')
        self.assertEqual(defaults.get('end_datetime'), datetime(2019, 6, 27, 15, 0), 'It should adjust to employee calendar: 0am -> 3pm')

    def test_create_no_resource_company_calendar_timezone(self):
        """ Test the default values are the company calendar hours with the timezone of the company """
        self.env.company.tz = 'Europe/Brussels'
        self.env.user.tz = 'Europe/Brussels'
        PlanningSlot = self.env['planning.slot'].with_context(
            tz='UTC',
            default_start_datetime='2019-06-25 00:00:00',
            default_end_datetime='2019-06-25 23:59:59',
            default_resource_ids=False)
        defaults = PlanningSlot.default_get(['resource_ids', 'start_datetime', 'end_datetime'])
        self.assertEqual(defaults.get('start_datetime'), datetime(2019, 6, 25, 6, 0), 'It should adapt the calendar hour to the company timezone: 8am -> 6am')
        self.assertEqual(defaults.get('end_datetime'), datetime(2019, 6, 25, 15, 0), 'It should adapt the calendar hour to the company timezone: 5pm -> 3pm')

    def test_unassign_employee_with_template(self):
        # we are going to put everybody in EDT, because if the employee has a different timezone from the company this workflow does not work.
        self.env.user.tz = 'America/New_York'
        self.env.user.company_id.tz = 'America/New_York'
        self.slot.template_id = self.template
        self.env.flush_all()
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 15, 0), 'It should set time from template, in user timezone (11am EDT -> 3pm UTC)')

        # simulate public user (no tz)
        self.env.user.tz = False
        self.slot.resource_ids = self.resource_janice
        self.env.flush_all()
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 15, 0), 'It should adjust to employee timezone')

        self.slot.resource_ids = False
        self.assertEqual(self.slot.template_id, self.template, 'It should keep the template')
        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 15, 0), 'It should reset to company calendar timezone: 11am EDT -> 3pm UTC')

    def test_compute_overlap_count(self):
        self.slot_6_2, self.slot_6_3, *_dummy = self.env['planning.slot'].create([
            {
                'resource_ids': self.resource_bert.ids,
                'start_datetime': datetime(2019, 6, 2, 8, 0),
                'end_datetime': datetime(2019, 6, 2, 17, 0),
            },
            {
                'resource_ids': self.resource_bert.ids,
                'start_datetime': datetime(2019, 6, 3, 8, 0),
                'end_datetime': datetime(2019, 6, 3, 17, 0),
            },
            {
                'resource_ids': self.resource_bert.ids,
                'start_datetime': datetime(2019, 6, 2, 10, 0),
                'end_datetime': datetime(2019, 6, 2, 12, 0),
            },
            {
                'resource_ids': self.resource_bert.ids,
                'start_datetime': datetime(2019, 6, 2, 16, 0),
                'end_datetime': datetime(2019, 6, 2, 18, 0),
            },
            {
                'resource_ids': self.resource_bert.ids,
                'start_datetime': datetime(2019, 6, 2, 18, 0),
                'end_datetime': datetime(2019, 6, 2, 20, 0),
            },
        ])
        self.assertEqual(2, self.slot_6_2.overlap_slot_count, '2 slots overlap')
        self.assertEqual(0, self.slot_6_3.overlap_slot_count, 'no slot overlap')

    def test_compute_datetime_with_template_slot(self):
        """ Test if the start and end datetimes of a planning.slot are correctly computed with the template slot

            Test Case:
            =========
            1) Create a planning.slot.template with start_hours = 11 am, end_hours = 2pm and duration_days = 2.
            2) Create a planning.slot for one day and add the template.
            3) Check if the start and end dates are on two days and not one.
            4) Check if the allocating hours is equal to the working hours of the resource.
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        template_slot = self.env['planning.slot.template'].create({
            'start_time': 11,
            'end_time': 14,
            'duration_days': 2,
        })

        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2021, 1, 4, 0, 0),
            'end_datetime': datetime(2021, 1, 4, 23, 59),
            'resource_ids': self.resource_bert.ids,
        })

        slot.write({
            'template_id': template_slot.id,
        })

        self.assertEqual(slot.start_datetime, datetime(2021, 1, 4, 11, 0), 'The start datetime should have the same hour and minutes defined in the template in the resource timezone.')
        self.assertEqual(slot.end_datetime, datetime(2021, 1, 5, 14, 0), 'The end datetime of this slot should be 3 hours after the start datetime as mentionned in the template in the resource timezone.')
        self.assertEqual(slot.allocated_hours, 10, 'The allocated hours of this slot should be the duration defined in the template in the resource timezone.')

    def test_compute_datetime_template_slot_24_7_calendar(self):
        """ A multi-day-span template on a 24/7 (0h-24h) calendar must not add a spurious minute.

            On a 0h-24h calendar, plan_days() returns the day's end as 23:59:59.999999; the
            end-datetime computation overwrote the hour and minute but kept the stale seconds,
            so an 8-hour shift was stored as 8h 1min and allocated_hours showed 08:01.
        """
        calendar_24_7 = self.env['resource.calendar'].create({
            'name': '24/7',
            'attendance_ids': [
                Command.create({'dayofweek': str(d), 'hour_from': 0, 'hour_to': 24, 'day_period': 'full_day'})
                for d in range(7)
            ],
        })
        self.employee_bert.resource_calendar_id = calendar_24_7
        template_slot = self.env['planning.slot.template'].create({
            'start_time': 16,
            'end_time': 0,
            'duration_days': 2,
        })
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2021, 1, 4, 0, 0),
            'end_datetime': datetime(2021, 1, 4, 23, 59),
            'resource_ids': [Command.set(self.resource_bert.ids)],
        })
        slot.write({'template_id': template_slot.id})

        self.assertEqual(slot.end_datetime, datetime(2021, 1, 5, 0, 0), 'The end datetime should land exactly on midnight, with no leftover seconds from the 24/7 calendar.')
        self.assertEqual(slot.allocated_hours, 8, 'An 8-hour shift should allocate exactly 8 hours, not 8h01.')

    def test_planning_state(self):
        """ The purpose of this test case is to check the planning state """
        self.slot.resource_ids = self.employee_bert.resource_id
        self.assertEqual(self.slot.state, '1_draft', 'Planning is draft mode.')
        self.slot.action_send()
        self.assertEqual(self.slot.state, '2_published', 'Planning is published.')

    def test_create_working_calendar_period(self):
        """ A default dates should be calculated based on the working calendar of the company whatever the period """
        self.env.company.tz = 'UTC'
        test = Form(self.env['planning.slot'].with_context(
            default_start_datetime=datetime(2019, 5, 27, 0, 0),
            default_end_datetime=datetime(2019, 5, 27, 23, 59, 59)
        ))
        slot = test.save()
        self.assertEqual(slot.start_datetime, datetime(2019, 5, 27, 6, 0), 'It should adjust to employee calendar: 8am -> 5pm')
        self.assertEqual(slot.end_datetime, datetime(2019, 5, 27, 15, 0), 'It should adjust to employee calendar: 8am -> 5pm')

        # For weeks period
        test_week = Form(self.env['planning.slot'].with_context(
            default_start_datetime=datetime(2019, 6, 23, 0, 0),
            default_end_datetime=datetime(2019, 6, 29, 23, 59, 59)
        ))

        test_week = test_week.save()
        self.assertEqual(test_week.start_datetime, datetime(2019, 6, 24, 6, 0), 'It should adjust to employee calendar: 8am -> 5pm')
        self.assertEqual(test_week.end_datetime, datetime(2019, 6, 28, 15, 0), 'It should adjust to employee calendar: 8am -> 5pm')

    def test_create_planing_slot_without_start_date(self):
        "Test to create planning slot with template id and without start date"
        planning_role = self.env['planning.role'].create({'name': 'role x'})
        template = self.env['planning.slot.template'].create({
            'start_time': 10,
            'end_time': 15,
            'duration_days': 1,
            'role_id': planning_role.id,
        })
        with Form(self.env['planning.slot']) as slot_form:
            slot_form.template_id = template
            slot_form.start_datetime = False
            slot_form.template_id = self.template
            self.assertEqual(slot_form.template_id, self.template)

    def test_shift_switching(self):
        """ The purpose of this test is to check the main back-end mechanism of switching shifts between employees """
        bert_user = new_test_user(self.env,
                                  login='bert_user',
                                  groups='planning.group_planning_user',
                                  name='Bert User',
                                  email='user@example.com')
        self.employee_bert.user_id = bert_user.id
        joseph_user = new_test_user(self.env,
                                    login='joseph_user',
                                    groups='planning.group_planning_user',
                                    name='Joseph User',
                                    email='juser@example.com')
        self.employee_joseph.user_id = joseph_user.id

        # Lets first try to switch a shift that is in the past - should throw an error
        self.slot.resource_ids = self.employee_bert.resource_id
        self.assertEqual(self.slot.is_past, True, 'The shift for this test should be in the past')
        with self.assertRaises(UserError):
            self.slot.with_user(bert_user).action_switch_shift()

        # Lets now try to switch a shift that is not ours - it should again throw an error
        self.assertEqual(self.slot.resource_ids, self.employee_bert.resource_id, 'The shift should be assigned to Bert')
        with self.assertRaises(UserError):
            self.slot.with_user(joseph_user).action_switch_shift()

        # Lets now to try to switch a shift that is both in the future and is ours - this should not throw an error
        test_slot = self.env['planning.slot'].create({
            'start_datetime': datetime.now() + relativedelta(days=2),
            'end_datetime': datetime.now() + relativedelta(days=4),
            'state': '2_published',
            'resource_ids': self.employee_bert.resource_id.ids,
        })

        with self.mock_mail_gateway():
            self.assertFalse(test_slot.switch_employee_ids, 'Before requesting to switch, the request to switch should be False')
            test_slot.with_user(bert_user).action_switch_shift()
            self.assertEqual(test_slot.switch_employee_ids, bert_user.employee_id, 'After the switch action, the request to switch should be True')

            # Lets now assign another user to the shift - this should remove the request to switch and assign the shift
            test_slot.with_user(joseph_user).action_self_assign()
            self.assertFalse(test_slot.switch_employee_ids, 'After the assign action, the request to switch should be False')
            self.assertEqual(test_slot.resource_ids, self.employee_joseph.resource_id, 'The shift should now be assigned to Joseph')

            # Lets now create a new request and then change the start datetime of the switch - this should remove the request to switch
            test_slot.with_user(joseph_user).action_switch_shift()
            self.assertEqual(test_slot.switch_employee_ids, joseph_user.employee_id, 'After the switch action, the request to switch should be True')
            test_slot.write({'start_datetime': (datetime.now() + relativedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")})
            self.assertFalse(test_slot.switch_employee_ids, 'After the change, the request to switch should be False')

        self.assertEqual(len(self._new_mails), 1)
        self.assertMailMailWEmails(
            [bert_user.partner_id.email],
            None,
            author=joseph_user.partner_id,
        )

    def test_shift_switching_multiple_employees(self):
        """ On a multi-employee shift, only the employees requesting a switch are recorded as
            requesters and replaced when someone takes the shift; the others stay assigned. """
        bert_user, joseph_user, janice_user = (
            new_test_user(self.env, login=f'{name}_switch_user', groups='planning.group_planning_user', name=name)
            for name in ('bert', 'joseph', 'janice')
        )
        self.employee_bert.user_id = bert_user
        self.employee_joseph.user_id = joseph_user
        self.employee_janice.user_id = janice_user
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime.now() + relativedelta(days=2),
            'end_datetime': datetime.now() + relativedelta(days=4),
            'state': '2_published',
            'resource_ids': (self.resource_bert + self.resource_joseph).ids,
        })

        # joseph asks to be replaced: only he is registered as a requester
        slot.with_user(joseph_user).action_switch_shift()
        self.assertEqual(slot.switch_employee_ids, self.employee_joseph, 'Only the requesting employee should be registered')
        self.assertEqual(slot.request_to_switch_msg, "joseph is looking for a replacement")
        self.assertEqual(slot.with_user(bert_user).request_to_switch_msg, "joseph is looking for a replacement",
                         'The message should also be readable by other users')

        # bert asks as well: both are requesters and the message mentions both
        slot.with_user(bert_user).action_switch_shift()
        self.assertEqual(slot.switch_employee_ids.sorted('id'), (self.employee_joseph + self.employee_bert).sorted('id'))
        self.assertIn("are looking for a replacement", slot.request_to_switch_msg)
        self.assertIn("bert", slot.request_to_switch_msg)
        self.assertIn("joseph", slot.request_to_switch_msg)

        # bert changes his mind: joseph still wants to switch, so the request remains
        slot.with_user(bert_user).action_cancel_switch()
        self.assertEqual(slot.switch_employee_ids, self.employee_joseph)
        self.assertEqual(slot.request_to_switch_msg, "joseph is looking for a replacement")

        # janice takes the shift: only joseph is replaced, bert stays assigned
        slot.with_user(janice_user).action_self_assign()
        self.assertEqual(slot.resource_ids.sorted('id'), (self.resource_bert + self.resource_janice).sorted('id'),
                         'Only the requesting employee should be replaced by the new assignee')
        self.assertFalse(slot.switch_employee_ids, 'The requesters should be reset once the switch is done')

    @freeze_time("2023-11-20")
    def test_shift_creation_from_role(self):
        self.env.user.tz = 'Asia/Kolkata'
        self.env.user.company_id.tz = 'Asia/Kolkata'
        PlanningRole = self.env['planning.role']
        PlanningTemplate = self.env['planning.slot.template']

        role_a = PlanningRole.create({'name': 'role a'})
        role_b = PlanningRole.create({'name': 'role b'})

        template_a = PlanningTemplate.create({
            'start_time': 8,
            'end_time': 10,
            'duration_days': 1,
            'role_id': role_a.id
        })
        self.assertEqual(template_a.duration_days, 1, "Duration in days should be a 1 day according to resource calendar.")
        self.assertEqual(template_a.end_time, 10.0, "End time should be 2 hours from start hours.")

        template_b = PlanningTemplate.create({
            'start_time': 8,
            'end_time': 12,
            'duration_days': 1,
            'role_id': role_b.id
        })

        slot = self.env['planning.slot'].create({'template_id': template_a.id})
        self.assertEqual(slot.role_id.id, slot.template_autocomplete_ids.mapped('role_id').id, "Role of the slot and shift template should be same.")

        slot.template_id = template_b.id
        self.assertEqual(slot.role_id.id, slot.template_autocomplete_ids.mapped('role_id').id, "Role of the slot and shift template should be same.")

    def test_manage_archived_resources(self):
        with self.mock_datetime_and_now("2020-04-22"):
            self.env.user.tz = 'UTC'
            slot_1, slot_2, slot_3 = self.env['planning.slot'].create([
                {
                    'resource_ids': self.resource_bert.ids,
                    'start_datetime': datetime(2020, 4, 20, 8, 0),
                    'end_datetime': datetime(2020, 4, 24, 17, 0),
                },
                {
                    'resource_ids': self.resource_bert.ids,
                    'start_datetime': datetime(2020, 4, 20, 8, 0),
                    'end_datetime': datetime(2020, 4, 21, 17, 0),
                },
                {
                    'resource_ids': self.resource_bert.ids,
                    'start_datetime': datetime(2020, 4, 23, 8, 0),
                    'end_datetime': datetime(2020, 4, 24, 17, 0),
                },
            ])

            slot1_initial_end_date = slot_1.end_datetime
            slot2_initial_end_date = slot_2.end_datetime

            departure = self.env['hr.employee.departure'].create([{
                'employee_id': self.resource_bert.employee_id.id,
                'dismissal_date': date(2020, 4, 22),
                'action_date': date(2020, 4, 22),
                'departure_reason_id': self.env.ref('hr.departure_fired').id,
            }])
            departure.action_register()

            self.assertEqual(slot_1.end_datetime, datetime.combine(fields.Date.today()+ timedelta(days=1), time.min), 'End date of the splited shift should be today')
            self.assertNotEqual(slot_1.end_datetime, slot1_initial_end_date, 'End date should be updated')
            self.assertEqual(slot_2.end_datetime, slot2_initial_end_date, 'End date should be the same')
            self.assertFalse(slot_3.resource_ids, 'Resource should be the False for archeived resource shifts')

    def test_avoid_rounding_error_when_creating_template(self):
        """
        Regression test: in some odd circumstances,
        a floating point error during the divmod conversion from float -> hours/min can lead to incorrect minutes
        5.1 after a divmod(1) gives back minutes = 0.0999999999964 instead of 1, hence the source of error
        """
        template = self.env['planning.slot.template'].create({
            'start_time': 8,
            'end_time': 13.1,
            'duration_days': 1,
        })
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2021, 1, 1, 0, 0),
            'end_datetime': datetime(2021, 1, 1, 23, 59),
        })
        slot.write({
            'template_id': template.id,
        })
        self.assertEqual(slot.end_datetime.minute, 6, 'The min should be 6, just like in the template, not 5 due to rounding error')

    def test_end_time_rounding_edge_case(self):
        """
        Test to ensure 0.996 doesn't round to 60,
        minutes need to be between 0 and 59.
        """
        shift_template = self.env['planning.slot.template'].create({
            'start_time': 8.995,
            'end_time': 17.996,
            'duration_days': 1,
        })
        self.assertEqual(re.sub(r'\s+', ' ', shift_template.name), '8:59 - 17:59')

    def test_copy_planning_shift(self):
        """ Test state of the planning shift is only copied once we are in the planning split tool

            Test Case:
            =========
            1) Create a planning shift with state published.
            2) Copy the planning shift as we are in the planning split tool (planning_split_tool=True in the context).
            3) Check the state of the new planning shift is published.
            4) Copy the planning shift as we are not in the planning split tool (planning_split_tool=False in the context).
            5) Check the state of the new planning shift is draft.
            6) Copy the planning shift without the context (= diplicate a shift).
            7) Check the state of the new planning shift is draft.
        """
        self.env.user.tz = 'UTC'
        slot = self.env['planning.slot'].create({
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2020, 4, 20, 8, 0),
            'end_datetime': datetime(2020, 4, 24, 17, 0),
            'state': '2_published',
        })
        self.assertEqual(slot.state, '2_published', 'The state of the shift should be published')

        slot1 = slot.with_context(planning_split_tool=True).copy()
        self.assertEqual(slot1.state, '2_published', 'The state of the shift should be copied')

        slot2 = slot.with_context(planning_split_tool=False).copy()
        self.assertEqual(slot2.state, '1_draft', 'The state of the shift should not be copied')

        slot3 = slot.copy()
        self.assertEqual(slot3.state, '1_draft', 'The state of the shift should not be copied')

    def test_calculate_slot_duration_flexible_hours(self):
        """ Ensures that _calculate_slot_duration function rounds up days only when there is an extra non-full day left """

        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'tz': 'UTC',
        })
        flexible_calendar = self.flexible_calendar_40_8
        employee.write({
            'resource_calendar_id': flexible_calendar.id,
        })

        # the diff between start and end is exactly 6 days
        planning_slot_1 = self.env['planning.slot'].create({
            'resource_ids': employee.resource_id.ids,
            'start_datetime': datetime(2024, 2, 23, 6, 0, 0),
            'end_datetime': datetime(2024, 2, 29, 6, 0, 0),
        })
        self.assertEqual(planning_slot_1.allocated_hours, 54.0, "day 23, 24 and 25 belong to week 8 (8*3 = 24h) / day 26, 27, 28 (8*3 = 24h) and 29 (6 hours from 0h to 6h) belong to week 9")

        # the diff between start and end is 6 days and 8 hours, hence the diff should be approximated to 7 days
        planning_slot_2 = self.env['planning.slot'].create({
            'resource_ids': employee.resource_id.ids,
            'start_datetime': datetime(2024, 2, 18, 8, 0, 0),
            'end_datetime': datetime(2024, 2, 24, 16, 0, 0),
        })
        self.assertEqual(planning_slot_2.allocated_hours, 40.0, "all days belong to same week = 8, allocated_hours is limited to 40 hours which is the week limit")

    def test_auto_plan_employee_with_break_company_no_breaks(self):
        """ Test auto-planning an employee with break, while company calendar without breaks

            Test Case:
            =========
            1) Create company calendar with 24 hours per day.
            2) Create employee with night shifts calendar, with 30 minutes break at midnight.
            3) Create shift from 21:30 to 6:00 with 8 allocated hours.
            4) Auto-plan the shift.
            5) Check the shift is assigned to the employee.
            6) Check the allocated hours remain the same.
        """
        # Create a 24-hour company calendar
        calendar_24hr = self.env['resource.calendar'].create({
            'name': '24/24 Company Calendar',
            'hours_per_day': 24.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 0, 'hour_to': 12})
                for day in range(7)
            ] + [
                (0, 0, {'dayofweek': str(day), 'hour_from': 12, 'hour_to': 24})
                for day in range(7)
            ],
        })
        self.env.user.company_id.resource_calendar_id = calendar_24hr

        night_shifts_calendar = self.env['resource.calendar'].create({
            'name': 'Night Shifts Calendar',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 21.5, 'hour_to': 24})
                for day in range(7)
            ] + [
                (0, 0, {'dayofweek': str(day), 'hour_from': 0.5, 'hour_to': 6})
                for day in range(7)
            ],
        })
        role = self.env['planning.role'].create({'name': 'test role'})
        # Create an employee linked to this calendar
        night_employee = self.env['hr.employee'].create({
            'name': 'Night employee',
            'resource_calendar_id': night_shifts_calendar.id,
            'default_planning_role_id': role.id,
            'tz': 'UTC',
        })

        # Create a shift from 21:30 to 6:00 with an allocated 8 hours
        night_shift = self.env['planning.slot'].create({
            'name': 'Night Shift',
            'start_datetime': datetime(2024, 5, 10, 21, 30),
            'end_datetime': datetime(2024, 5, 11, 6, 0),
            'role_id': role.id,
        })
        night_shift.allocated_hours = 8
        # Execute auto-plan to assign the employee
        night_shift.auto_plan_id()

        self.assertEqual(night_shift.resource_ids, night_employee.resource_id, 'The night shift should be assigned to the night employee')
        self.assertEqual(night_shift.allocated_hours, 8, 'The allocated hours should remain the same')
        self.assertEqual(night_shift.allocated_percentage, 100, 'The allocated percentage should be 100% as the resource will work the allocated hours')

    def test_auto_plan_undo_preserves_allocated_hours(self):
        """
            When undoing auto-plan, the system should preserve the original allocated_hours.
            Test Case:
            =========
            1) Create an open shift with 6 allocated hours.
            2) Auto-plan the shift to assign it to a resource.
            3) Verify the shift is assigned and allocated_hours remains 6.
            4) Undo the auto-plan assignment.
            5) Check allocated_hours is still 6.
        """
        start_dt = datetime(2025, 12, 25, 9, 0, 0)
        end_dt = datetime(2025, 12, 25, 17, 0, 0)
        role = self.env['planning.role'].create({'name': 'Developer Test Role'})
        self.employee_joseph.default_planning_role_id = role.id
        open_shift = self.env['planning.slot'].create({
            'start_datetime': start_dt,
            'end_datetime': end_dt,
            'allocated_hours': 6.0,
            'resource_ids': False,
            'role_id': role.id,
        })

        self.assertEqual(open_shift.allocated_hours, 6.0, 'Initial allocated_hours should be 6.0')
        self.assertFalse(open_shift.resource_ids, 'Should be an open shift')

        result = self.env['planning.slot'].with_context(
            default_start_datetime=start_dt,
            default_end_datetime=end_dt,
        ).auto_plan_ids([('id', '=', open_shift.id)])

        open_shift_assigned = result.get('open_shift_assigned', [])

        self.assertEqual(len(open_shift_assigned), 1, 'One shift should be assigned')
        open_shift.invalidate_recordset()
        self.assertTrue(open_shift.resource_ids, 'Shift should be assigned to a resource')
        self.assertEqual(open_shift.allocated_hours, 6.0, 'allocated_hours should still be 6.0 after auto-plan')

        self.env['planning.slot'].action_rollback_auto_plan_ids(result)

        open_shift.invalidate_recordset()
        self.assertFalse(open_shift.resource_ids, 'Shift should be back to open state')
        self.assertEqual(open_shift.allocated_hours, 6.0, 'allocated_hours should be preserved at 6.0 after undo')

    def test_write_multiple_slots(self):
        """ Test that we can write a resource_ids on multiple slots at once. """
        slots = self.env['planning.slot'].create([
            {'start_datetime': datetime(2024, 5, 10, 8, 0), 'end_datetime': datetime(2024, 5, 10, 17, 0)},
            {'start_datetime': datetime(2024, 6, 10, 8, 0), 'end_datetime': datetime(2024, 6, 10, 17, 0)},
        ])
        slots.write({'resource_ids': self.resource_bert.ids})
        self.assertEqual(slots.resource_ids, self.resource_bert)

    def test_write_without_resource(self):
        slot = self.env['planning.slot'].create(
            {'start_datetime': datetime(2024, 5, 10, 8, 0), 'end_datetime': datetime(2024, 5, 10, 17, 0)}
        )
        slot.write({
            'repeat' : True,
            'recurrence_update': 'all',
            'start_datetime': datetime(2024, 5, 10, 9, 0),
            'end_datetime': datetime(2024, 5, 10, 18, 0),
        })
        self.assertRecordValues(slot, [{
            'repeat': True,
            'start_datetime': datetime(2024, 5, 10, 9, 0),
            'end_datetime': datetime(2024, 5, 10, 18, 0),
        }])

    def test_compute_company_planning_slot(self):
        self.assertEqual(self.slot.company_id, self.env.company, "The slot's company should be the current one.")
        company = self.env['res.company'].create({"name": "Test company"})
        self.resource_bert.company_id = company
        self.slot.resource_ids = self.resource_bert
        self.assertEqual(self.slot.company_id, company, "The slot's company should be the resource's one.")

    def test_flexible_contract_slot(self):
        """
            A flexible contract should have no constraints on the slots in terms of start/end time,
            but the duration cannot exceed the hours_per_day defined in the contract.
        """
        # Create a shift longer than the calendar's hours_per_day
        flexible_calendar = self.flexible_calendar_50_10
        self.employee_bert.write({
            'resource_calendar_id': flexible_calendar.id,
        })
        slot = self.env['planning.slot'].create({
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2022, 1, 11, 3, 0),
            'end_datetime': datetime(2022, 1, 11, 23, 0),
            'state': '2_published',
        })
        self.assertEqual(slot.allocated_hours, 10.0, 'The allocated hours should be 10.0')
        self.assertEqual(slot.allocated_percentage, 100, 'The allocated percentage should be 100%%')

        # Create a night shift that spans over two days, but shorter than the calendar's hours_per_day
        slot = self.env['planning.slot'].create({
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2022, 1, 12, 22, 0),
            'end_datetime': datetime(2022, 1, 13, 4, 0),
            'state': '2_published',
        })
        self.assertEqual(slot.allocated_hours, 6.0, 'The allocated hours should be 6.0')
        self.assertEqual(slot.allocated_percentage, 100, 'The allocated percentage should be 100%%')

        # Create a night shift that spans over two days and is longer than the calendar's hours_per_day
        slot = self.env['planning.slot'].create({
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2022, 1, 13, 20, 0),
            'end_datetime': datetime(2022, 1, 14, 10, 0),
            'state': '2_published',
        })
        self.assertEqual(slot.allocated_hours, 14.0, '4 hours available on day 13, 10 hours available on day 14, no daily limit excedded in both days')
        self.assertEqual(slot.allocated_percentage, 100, 'The allocated percentage should be 100%%')

        # Changing the allocated time percentage should be reflected in the allocated hours
        slot.allocated_percentage = 50
        self.assertEqual(slot.allocated_hours, 7.0, 'The allocated hours should be 5.0 after changing the allocated percentage to 50%%')

    def test_fully_flexible_contract_slot(self):
        """
            A fully flexible contract should not have any constraints on the slots in terms of duration and start time.
        """
        fully_flexible_calendar = self.fully_flexible_calendar
        self.employee_bert.resource_calendar_id = fully_flexible_calendar
        slot = self.env['planning.slot'].create({
            'resource_ids': self.resource_bert.ids,
            'start_datetime': datetime(2022, 1, 11, 4, 0),
            'end_datetime': datetime(2022, 1, 12, 22, 0),
            'state': '2_published',
        })
        self.assertEqual(slot.allocated_hours, 42.0, 'The allocated hours should be 42.0')
        self.assertEqual(slot.allocated_percentage, 100, 'The allocated percentage should be 100%%')

        # Changing the allocated time percentage should be reflected in the allocated hours
        slot.allocated_percentage = 50
        self.assertEqual(slot.allocated_hours, 21.0, 'The allocated hours should be 21.0 after changing the allocated percentage to 50%%')

    def test_open_shift_planning_slot_including_weekend(self):
        """
            When an open shift is scheduled spanning between weekday and weekends (e.g. Sunday 8 AM to Monday 5 PM),
            allocated time should be equal to 16h instead of 8h (same behavior as for employees working flexible hours):
        """
        slot = self.env['planning.slot'].create({
            'resource_ids': False,
            'start_datetime': datetime(2022, 1, 16, 8, 0),  # Sunday 8AM
            'end_datetime': datetime(2022, 1, 17, 17, 0),   # Monday 5PM
            'state': '2_published',
        })
        self.assertEqual(slot.allocated_hours, 16.0, 'The allocated hours should be 16.0 for the open shift')
        self.assertEqual(slot.allocated_percentage, 100, 'The allocated percentage should be 100%%')

    @freeze_time('2021-01-01')
    def test_allocated_hours_when_template_is_during_a_break(self):
        self.resource_janice.tz = 'UTC'
        template_slot = self.env['planning.slot.template'].create({
            'start_time': 11,
            'end_time': 16,
        })

        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2021, 1, 1, 0, 0),
            'end_datetime': datetime(2021, 1, 1, 23, 59),
            'resource_ids': self.resource_janice.ids,
        })

        slot.write({
            'template_id': template_slot.id,
        })

        self.assertEqual(slot.start_datetime, datetime(2021, 1, 1, 11, 0))
        self.assertEqual(slot.end_datetime, datetime(2021, 1, 1, 16, 0))
        self.assertEqual(slot.allocated_hours, 4)

    def test_allocated_hours_shift_duplication(self):
        self.slot.resource_ids = self.resource_joseph
        self.assertEqual(self.slot.allocated_hours, 8)
        slot2 = self.slot.copy({'resource_ids': self.resource_bert.ids})
        self.assertEqual(slot2.allocated_hours, 4, "The allocated hours should have been recomputed with the new resource after copying the shift.")

    def test_planning_expand_resource(self):
        """
            When planning_expand_resource = True and there are slots assigned to the resource in the previous or next period,
            the resource is also displayed in the gantt view with value = 0.
        """
        flexible_calendar = self.flexible_calendar_50_10
        self.employee_bert.write({
            'resource_calendar_id': flexible_calendar.id,
        })
        self.slot.resource_ids = self.employee_bert.resource_id
        group_by = ['resource_ids']

        planned_dates = [
            ('2019-07-01 00:00:00', '2019-07-31 23:59:59'),
            ('2019-08-01 00:00:00', '2019-08-31 23:59:59')
        ]
        for case, (start_date, stop_date) in enumerate(planned_dates):
            result = self.env['planning.slot'].with_context(planning_expand_resource=True).get_gantt_data([
                '&',
                ['start_datetime', '<', stop_date],
                ['end_datetime', '>', start_date],
            ], group_by, {'display_name': {}}, unavailability_fields=group_by, progress_bar_fields=group_by, start_date=start_date, stop_date = stop_date,scale='month')

            if case == 0:
                self.assertTrue(self.slot.resource_ids.id in result['progress_bars']['resource_ids'], "Resource has slots in the previous month")
                self.assertEqual(result['progress_bars']['resource_ids'][self.slot.resource_ids.id]['value'], 0.0)
            else:
                self.assertFalse(self.slot.resource_ids.id in result['progress_bars']['resource_ids'])

    def test_gantt_progress_bar_multiple_resources_different_calendars(self):
        """
        When several resources are assigned to the same slot, the hours in the
        progress bar of each resource should reflect its own working hours.
        """
        self.slot.resource_ids = self.employee_joseph.resource_id + self.employee_bert.resource_id

        # calendar_joseph: Thursday 9-13 and 14-18 (8h), calendar_bert: Thursday 13-17 (4h)
        self.assertEqual(self.slot.allocated_hours, 12, "Allocated hours should be the sum of both resources' working hours")

        planning_hours_info = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', (self.employee_joseph.resource_id + self.employee_bert.resource_id).ids,
            datetime(2019, 6, 24), datetime(2019, 6, 30, 23, 59)
        )

        self.assertEqual(planning_hours_info[self.employee_joseph.resource_id.id]['value'], 8)
        self.assertEqual(planning_hours_info[self.employee_bert.resource_id.id]['value'], 4)

    def test_allocated_hours_open_shift(self):
        """ Ensure that the allocated hours for an open shift are correctly computed based on the
        company calendar. """
        self.employee_joseph.user_id = self.env.user.id
        PlanningSlot = self.env["planning.slot"]

        # Create a slot NOT during the employee working hours
        slot = PlanningSlot.create({
            'start_datetime': datetime(2019, 5, 1, 8, 0),
            'end_datetime': datetime(2019, 5, 1, 17, 0),
        })
        self.assertEqual(
            slot.allocated_hours,
            8.0,
            "The allocated hours should be 8.0 for the open shift based on the company calendar",
        )

        # Create a slot during the employee working hours
        slot = PlanningSlot.create({
            'start_datetime': datetime(2019, 5, 2, 8, 0),
            'end_datetime': datetime(2019, 5, 2, 17, 0),
        })
        self.assertEqual(
            slot.allocated_hours,
            8.0,
            "The allocated hours should be 8.0 for the open shift based on the company calendar",
        )

    def test_planning_slot_default_datetime(self):
        """ This test ensures that when selecting the datetime in Gantt view, the default hours are set correctly """
        self.resource_joseph.tz = 'Europe/Brussels'
        PlanningSlot = self.env['planning.slot'].with_user(self.env.user).with_context(
            default_start_datetime='2026-03-19 13:00:00',
            default_end_datetime='2026-03-19 15:00:00',
            default_resource_ids=self.resource_joseph.ids,
        )
        slot = PlanningSlot.default_get(['resource_ids', 'start_datetime', 'end_datetime'])
        self.assertEqual(slot.get('start_datetime'), datetime(2026, 3, 19, 13, 0, 0), "The slot start datetime should be matched to the resource's timezone")
        self.assertEqual(slot.get('end_datetime'), datetime(2026, 3, 19, 15, 0, 0), "The slot end datetime should be matched to the resource's timezone")

    def test_copy_shift_without_archive_resource(self):
        self.slot.resource_ids = self.resource_joseph
        self.slot2.resource_ids = self.resource_bert
        self.resource_joseph.action_archive()
        slots = self.slot + self.slot2
        slot, slot2 = slots.copy()
        self.assertFalse(slot.resource_ids)
        self.assertEqual(slot2.resource_ids, self.resource_bert)

        # Exception we keep the archived resource if it is given in parameter of copy method
        slot, slot2 = slots.copy({'resource_ids': self.resource_joseph.ids})
        self.assertEqual(slot.with_context(active_test=False).resource_ids, self.resource_joseph)
        self.assertEqual(slot2.with_context(active_test=False).resource_ids, self.resource_joseph)

        # Exception we keep the archived resource if the shift is split
        slot = self.slot.with_context(planning_split_tool=True).copy()
        self.assertEqual(slot.with_context(active_test=False).resource_ids, self.resource_joseph)

    def test_unavailability_open_shift(self):
        """ Ensure that there is no unavailabilities for open shifts. """
        gantt_unavailabilities = self.env['planning.slot']._gantt_unavailability(
            'resource_ids',
            self.resource_bert.ids,
            datetime(2024, 1, 1),
            datetime(2024, 1, 7),
            'month',
        )
        self.assertNotEqual(
            gantt_unavailabilities[False],
            [],
            'There should be unavailabilities for open shifts since Bert has a fixed schedule.'
        )
        self.assertNotEqual(gantt_unavailabilities[self.resource_bert.id], [], 'There should be unavailabilities for Bert.')

    def test_unavailability_open_shift_with_flexible_worker(self):
        """ Ensure that open shifts have NO unavailabilities if a flexible worker is in the view. """
        self.resource_bert.calendar_id = self.fully_flexible_calendar
        gantt_unavailabilities = self.env['planning.slot']._gantt_unavailability(
            'resource_ids',
            self.resource_bert.ids,
            datetime(2024, 1, 1),
            datetime(2024, 1, 7),
            'month',
        )
        self.assertEqual(
            gantt_unavailabilities[False],
            [],
            'There should be no unavailability for open shifts because a flexible worker is present.'
        )

    def test_batch_creation_from_calendar(self):
        """
        This test ensure that when planning slots are created from the "create multi" of the calendar view inconsistent slot
        are not created.
        employee with standard calendar : the slot is valid if it is contained at least partially in the employee's schedule.
        e.a. employee with 9-17 working schedule. slot 8-12 is valid. slot 18-20 is invalid.
        employee with flexible working hours : all slots are valid.
        """
        template_valid, template_invalid = self.env['planning.slot.template'].create([{
            'start_time': 8, 'end_time': 12, 'duration_days': 1,
        }, {
            'start_time': 18, 'end_time': 20, 'duration_days': 1,
        }])
        fully_flexible_calendar = self.fully_flexible_calendar
        self.employee_bert.resource_calendar_id = fully_flexible_calendar
        self.employee_joseph.resource_calendar_id = self.company_calendar
        slot_joseph, slot_bert = self.env['planning.slot'].create_batch_from_calendar([{
                'start_datetime': '2025-04-04 08:00:00', 'end_datetime': '2025-04-04 12:00:00',
                'resource_ids': resource.ids, 'template_id': template_valid.id,
            } for resource in (self.resource_joseph, self.resource_bert)
        ])

        self.assertEqual(slot_joseph.resource_ids, self.resource_joseph)
        self.assertEqual(slot_joseph.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 08:00:00')
        self.assertEqual(slot_joseph.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 12:00:00')
        self.assertEqual(slot_bert.resource_ids, self.resource_bert)
        self.assertEqual(slot_bert.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 08:00:00')
        self.assertEqual(slot_bert.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 12:00:00')

        slot_bert = self.env['planning.slot'].create_batch_from_calendar([{
                'start_datetime': '2025-04-04 18:00:00', 'end_datetime': '2025-04-04 20:00:00',
                'resource_ids': resource.ids, 'template_id': template_invalid.id,
            } for resource in (self.resource_joseph, self.resource_bert)
        ])
        self.assertEqual(slot_bert.resource_ids, self.resource_bert)
        self.assertEqual(slot_bert.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 18:00:00')
        self.assertEqual(slot_bert.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-04 20:00:00')

    def test_batch_creation_from_calendar_with_duration_days_template(self):
        """
        This test ensure that when planning slots are created from the "create multi" of the calendar view with shift
        template with duration days > 1, then the unavailable days are skipped.
        Test case :
            Create 2 new slots for Bert, flexible employee.
            - weekend are ignored.
            - start dates : Monday 07, Tuesday 08
            - expected end dates : Friday 11, Saturday 12
            Create 2 new slots for Joseph, fixed schedule 40h
            - weekend are computed
            - start dates : Monday 07, Tuesday 08
            - expected end dates: Friday 11, Monday 14
        """
        shift_template = self.env['planning.slot.template'].create({
            'start_time': 8, 'end_time': 12, 'duration_days': 5
        })
        fully_flexible_calendar = self.fully_flexible_calendar
        self.employee_bert.resource_calendar_id = fully_flexible_calendar
        self.employee_joseph.resource_calendar_id = self.company_calendar

        slot_joseph_1, slot_bert_1, slot_joseph_2, slot_bert_2 = self.env['planning.slot'].create_batch_from_calendar([{
                'start_datetime': f'2025-04-{day[0]} 08:00:00', 'end_datetime': f'2025-04-{day[1]} 12:00:00',
                'resource_ids': resource.ids, 'template_id': shift_template.id,
            } for day in [['07', '11'], ['08', '12']] for resource in (self.resource_joseph, self.resource_bert)
        ])
        self.assertEqual(slot_joseph_1.resource_ids, self.resource_joseph)
        self.assertEqual(slot_joseph_2.resource_ids, self.resource_joseph)
        self.assertEqual(slot_bert_1.resource_ids, self.resource_bert)
        self.assertEqual(slot_bert_2.resource_ids, self.resource_bert)
        self.assertEqual(slot_joseph_1.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-07 08:00:00')
        self.assertEqual(slot_joseph_2.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-08 08:00:00')
        self.assertEqual(slot_bert_1.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-07 08:00:00')
        self.assertEqual(slot_bert_2.start_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-08 08:00:00')
        self.assertEqual(slot_joseph_1.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-11 12:00:00')
        self.assertEqual(slot_joseph_2.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-14 12:00:00')
        self.assertEqual(slot_bert_1.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-11 12:00:00')
        self.assertEqual(slot_bert_2.end_datetime.strftime('%Y-%m-%d %H:%M:%S'), '2025-04-12 12:00:00')

    def test_batch_creation_from_calendar_adds_assigned_materials(self):
        material = self.env['resource.resource'].create({
            'name': "Material Resource",
            'resource_type': 'material',
            'assigned_employee_id': self.employee_joseph.id,
        })
        shift_template = self.env['planning.slot.template'].create({
            'start_time': 8, 'end_time': 12, 'duration_days': 5
        })
        slot_joseph, slot_bert = self.env['planning.slot'].create_batch_from_calendar([{
                'start_datetime': '2025-04-07 08:00:00', 'end_datetime': '2025-04-11 12:00:00',
                'resource_ids': resource.ids, 'template_id': shift_template.id,
            } for resource in (self.resource_joseph, self.resource_bert)
        ])
        self.assertEqual(self.resource_joseph + material, slot_joseph.resource_ids)
        self.assertEqual(self.resource_bert, slot_bert.resource_ids)

    def test_copy_slots_when_time_off(self):
        """
        week_1: 19-01-2020 -> 25-01-2020
            original slot: 20-01-2020 08:00 -> 24-01-2020 17:00 (5 days)
            allocated_hours: 50 hours and allocated_percentage: 125
        --------------------------------------------------------------------------------------------
        week_2: 26-01-2020 -> 01-02-2020
            resource on leave: 28-01-2020 8:00 -> 29-01-2020 17:00 (2 days i.e 16 hours)
            copy slot: 27-01-2020 08:00 -> 31-01-2020 17:00
        -------------------------------------------------------------------------------------------
        Expected result:
        Total 4 slots will create, 3 slot assigned to resource and 1 open slot
            1) 27-01-2020 08:00 -> 27-01-2020 12:00 (4 hrs)(assigned slot)
            2) 27-01-2020 13:00 -> 27-01-2020 19:00 (4 hrs)(assigned slot)
            3) 28-01-2020 08:00 -> 29-01-2020 19:00 (16 hrs)(open slot)
            4) 30-01-2020 08:00 -> 31-01-2020 19:00 (16 hrs)(assigned slot)
        """
        employee_bert = self.env['hr.employee'].create({
            'name': 'Test',
            'work_email': 'test@test.in',
            'tz': 'UTC',
            'create_date': '2015-01-01 00:00:00',
            'resource_calendar_id': self.company_calendar.id,
        })

        PlanningSlot = self.env['planning.slot']
        dt = datetime(2020, 1, 20, 0, 0)

        slot = PlanningSlot.create({
            'resource_ids': employee_bert.resource_id.ids,
            'start_datetime': dt + relativedelta(hours=8),
            'end_datetime': dt + relativedelta(days=4, hours=17),
        })

        self.env['resource.calendar.leaves'].create({
            'name': "I go to my father-in-law's",
            'calendar_id': employee_bert.resource_id.calendar_id.id,
            'date_from': dt + relativedelta(weeks=1, days=1),
            'date_to': dt + relativedelta(weeks=1, days=2, hours=17),
            'resource_id': employee_bert.resource_id.id,
        })

        copied, _dummy = PlanningSlot.action_copy_previous_week(
            str(dt + relativedelta(weeks=1)), [
                ['start_datetime', '<=', dt + relativedelta(weeks=1)],
                ['end_datetime', '>=', dt],
                ['resource_ids', '=', employee_bert.resource_id.id],
            ]
        )

        copied_slot = PlanningSlot.browse(copied)
        open_slot = copied_slot.filtered(lambda x: not x.resource_ids)

        self.assertEqual(len(open_slot), 4, "4 shift should be copied as open, as the employee is on off")
        self.assertEqual(sum(open_slot.mapped('allocated_hours')), 16, "16 hours should be allocated to open slot")
        self.assertEqual(slot.allocated_hours, sum(copied_slot.mapped('allocated_hours')),
            "The allocated hours of slot and allocated hours of copied slots must be same")

    def test_change_planning_template_start_or_end_time_to_invalid_value(self):
        with self.assertRaises(ValidationError):
            self.template.write({'end_time': 24})
            self.template.read()
        with self.assertRaises(ValidationError):
            self.template.write({'start_time': 24})
            self.template.read()
        self.assertEqual(self.template.end_time, 14)
        self.assertEqual(self.template.start_time, 11)

    def test_auto_plan_flexible_employee_no_rate_no_hours_day_overload(self):
        self.env.user.tz = 'UTC'
        shift1, shift2 = self.env['planning.slot'].create([{
            'name': 'Night Shift',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime': datetime(2023, 7, 28, 16, 0),
            'role_id': self.flex_role.id,
            'allocated_hours': 4,
        }, {
            'name': 'Night Shift',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime': datetime(2023, 7, 28, 16, 0),
            'role_id': self.flex_role.id,
            'allocated_hours': 3,
        }])

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-01 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift1.id, shift2.id])
        self.assertEqual(shift1.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift2.resource_ids.employee_id, self.flex_employee)

        self.assertEqual(shift1.allocated_hours, 4.0, "should be the same original value")
        self.assertEqual(shift1.allocated_percentage, 50.0, "4 allocated hours / 8 working hours")

        self.assertEqual(shift2.allocated_hours, 3.0, "should be the same original value")
        self.assertEqual(shift2.allocated_percentage, 37.5, "4 allocated hours / 8 working hours")

        shift3, shift4 = self.env['planning.slot'].create([{
            'name': 'Night Shift',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime': datetime(2023, 7, 28, 16),
            'role_id': self.flex_role.id,
            'allocated_hours': 1,
        }, {
            'name': 'Night Shift',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime': datetime(2023, 7, 28, 16),
            'role_id': self.flex_role.id,
            'allocated_hours': 2,
        }])

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-01 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift3.id], "shift 4 cannot be planned as it will create an overload")
        self.assertEqual(shift3.resource_ids.employee_id, self.flex_employee, "allocated_hours = 4 + 3 + 1 = 8 hours / allocated_percentage = 50 + 12.5 + 37.5 = 100%")
        self.assertFalse(shift4.resource_ids.employee_id)

        self.assertEqual(shift3.allocated_hours, 1.0, "should be the same original value")
        self.assertEqual(shift3.allocated_percentage, 12.5, "1 allocated hour / 8 working hours")

        shift5 = self.env['planning.slot'].create({
            'name': 'Night Shift',
            'start_datetime': datetime(2023, 7, 28, 6),
            'end_datetime': datetime(2023, 7, 28, 8),
            'role_id': self.flex_role.id,
            'allocated_hours': 2,
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-01 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [], "8 hours already consumed on day 28 from 8h to 16h")

        flexible_calendar = self.flexible_calendar_40_8
        self.employee_bert.write({
            'resource_calendar_id': flexible_calendar.id,
            'default_planning_role_id': self.flex_role.id,
            'tz': 'UTC',
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-01 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift4.id, shift5.id])
        self.assertEqual(shift4.resource_ids.employee_id, self.employee_bert)
        self.assertEqual(shift5.resource_ids.employee_id, self.employee_bert)

        self.assertEqual(shift4.allocated_hours, 2.0, "should be the same original value")
        self.assertEqual(shift4.allocated_percentage, 25.0, "2 allocated hours / 8 working hours")

        self.assertEqual(shift5.allocated_hours, 2.0, "should be the same original value")
        self.assertEqual(shift5.allocated_percentage, 100.0, "2 allocated hour / 2 working hours")

    def test_auto_plan_fully_flexible_employee_no_rate_no_hours_day_overload(self):
        self.env.user.tz = 'UTC'
        self.flex_employee.resource_calendar_id.write({
            'hours_per_week': 0,
            'hours_per_day': 0,
        })
        shift1, shift2, shift3, shift4 = self.env['planning.slot'].create([{
            'name': 'Shift 1',
            'start_datetime': datetime(2023, 7, 28, 2),
            'end_datetime': datetime(2023, 7, 28, 23),
            'role_id': self.flex_role.id,
            'allocated_hours': 10.5,
        }, {
            'name': 'Shift 2',
            'start_datetime': datetime(2023, 7, 28, 2),
            'end_datetime': datetime(2023, 7, 28, 23),
            'role_id': self.flex_role.id,
            'allocated_hours': 10.5,
        }, {
            'name': 'Shift 3',
            'start_datetime': datetime(2023, 7, 28, 0),
            'end_datetime': datetime(2023, 7, 28, 2),
            'role_id': self.flex_role.id,
            'allocated_hours': 2,
        }, {
            'name': 'Shift 4',
            'start_datetime': datetime(2023, 7, 28, 23),
            'end_datetime': datetime(2023, 7, 29),
            'role_id': self.flex_role.id,
            'allocated_hours': 1,
        }])

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-01 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift1.id, shift2.id, shift3.id, shift4.id])
        self.assertEqual(shift1.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift2.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift3.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift4.resource_ids.employee_id, self.flex_employee)

        self.assertEqual(shift1.allocated_hours, 10.5, "should be the same original value")
        self.assertEqual(shift1.allocated_percentage, 50.0, "10.5 allocated hours / 21 working hours from 2h to 23h")

        self.assertEqual(shift2.allocated_hours, 10.5, "should be the same original value")
        self.assertEqual(shift2.allocated_percentage, 50.0, "10.5 allocated hours / 21 working hours from 2h to 23h")

        self.assertEqual(shift3.allocated_hours, 2.0, "should be the same original value")
        self.assertEqual(shift3.allocated_percentage, 100.0, "2 allocated hours / 2 working hours from 0h to 2h")

        self.assertEqual(shift4.allocated_hours, 1.0, "should be the same original value")
        self.assertEqual(shift4.allocated_percentage, 100.0, "1 allocated hour / 1 working hours from 23h to 0h (next day)")

        self.env['planning.slot'].create({
            'name': 'Night Shift',
            'start_datetime': datetime(2023, 7, 28, 8),
            'end_datetime': datetime(2023, 7, 28, 16),
            'role_id': self.flex_role.id,
            'allocated_hours': 1,
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2023-07-26 22:00:00",
            default_end_datetime="2023-08-01 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2023-08-01 22:00:00'], ['end_datetime', '>', '2023-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [], "employee already busy for the 24 hours on day 28")

    def test_auto_plan_flexible_employee_no_week_overload(self):
        self.env.user.tz = 'UTC'

        shift1, shift2, shift3, shift4, shift5 = self.env['planning.slot'].create([{
            'name': 'Shift 1',
            'start_datetime': datetime(2025, 7, 28, 8),
            'end_datetime': datetime(2025, 7, 30, 16),
            'role_id': self.flex_role.id,
            'allocated_hours': 12,
        }, {
            'name': 'Shift 2',
            'start_datetime': datetime(2025, 7, 28, 8),
            'end_datetime': datetime(2025, 7, 30, 16, 0),
            'role_id': self.flex_role.id,
            'allocated_hours': 12,
        }, {
            'name': 'Shift 3',
            'start_datetime': datetime(2025, 7, 31, 8),
            'end_datetime': datetime(2025, 7, 31, 16),
            'role_id': self.flex_role.id,
            'allocated_hours': 8,
        }, {
            'name': 'Shift 4',
            'start_datetime': datetime(2025, 8, 1, 8),
            'end_datetime': datetime(2025, 8, 1, 16),
            'role_id': self.flex_role.id,
            'allocated_hours': 8,
        }, {
            'name': 'Shift 5',
            'start_datetime': datetime(2025, 8, 2, 8),
            'end_datetime': datetime(2025, 8, 2, 16, 0),
            'role_id': self.flex_role.id,
            'allocated_hours': 8,
        }])

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2025-07-26 22:00:00",
            default_end_datetime="2025-08-04 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2025-08-04 22:00:00'], ['end_datetime', '>', '2025-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift1.id, shift2.id, shift3.id, shift4.id], "shift 5 cannot be planned as it will create an overload on the week")
        self.assertEqual(shift1.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift2.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift3.resource_ids.employee_id, self.flex_employee)
        self.assertEqual(shift4.resource_ids.employee_id, self.flex_employee)
        self.assertFalse(shift5.resource_ids.employee_id)

        # assert _compute_allocated_hours works fine for flexible resources (triggered after setting the resource on the shift, then again when setting the allocated hours)
        self.assertEqual(shift1.allocated_hours, 12.0, "should be the same original value")
        self.assertEqual(shift1.allocated_percentage, 50.0, "12 allocated hours / 24 working hours from 8h day 28 to 16h day 30")

        self.assertEqual(shift2.allocated_hours, 12.0, "should be the same original value")
        self.assertEqual(shift2.allocated_percentage, 50.0, "12 allocated hours / 24 working hours from 8h day 28 to 16h day 30")

        self.assertEqual(shift3.allocated_hours, 8.0, "should be the same original value")
        self.assertEqual(shift3.allocated_percentage, 100.0, "8 allocated hours / 8 working hours from 8h to 16h day 31")

        self.assertEqual(shift4.allocated_hours, 8.0, "should be the same original value")
        self.assertEqual(shift4.allocated_percentage, 100.0, "8 allocated hours / 8 working hours from 8h to 16h day 01")

    def test_auto_plan_fully_flexible_employee_no_hours_limit_per_week(self):
        self.env.user.tz = 'UTC'
        self.flex_employee.resource_calendar_id.write({
            'hours_per_week': 0,
            'hours_per_day': 0,
        })

        shift = self.env['planning.slot'].create({
            'name': 'Shift 1',
            'start_datetime': datetime(2025, 7, 27),
            'end_datetime': datetime(2025, 8, 2),
            'role_id': self.flex_role.id,
            'allocated_hours': 120.0,
        })

        res = self.env["planning.slot"].with_context(
            default_start_datetime="2025-07-26 22:00:00",
            default_end_datetime="2025-08-04 22:00:00",
        ).auto_plan_ids(['&', ['start_datetime', '<', '2025-08-04 22:00:00'], ['end_datetime', '>', '2025-07-26 22:00:00']])

        self.assertEqual(res['open_shift_assigned'], [shift.id])
        self.assertEqual(shift.resource_ids.employee_id, self.flex_employee)

    def test_gantt_progress_bar_split_when_flexible(self):
        """
        Test if a slot is shared between two weeks the progress bar
        should be split between both weeks. Not showing the whole allocated
        hours in both weeks.
        """
        flexible_calendar = self.flexible_calendar_40_8
        self.employee_bert.write({
            'resource_calendar_id': flexible_calendar.id,
        })

        dt = datetime(2025, 8, 22, 0, 0)

        self.slot.write({
            'resource_ids': self.employee_bert.resource_id.ids,
            'start_datetime': dt + relativedelta(hours=8),
            'end_datetime': dt + relativedelta(days=4, hours=17),
        })

        planning_hours_info_1st_week = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', self.employee_bert.resource_id.ids, datetime(2025, 8, 16), datetime(2025, 8, 23, 23, 59)
        )

        self.assertEqual(self.slot.allocated_hours, 40.0)
        self.assertEqual(planning_hours_info_1st_week[self.employee_bert.resource_id.id]['value'], 16)

        planning_hours_info_2nd_week = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', self.employee_bert.resource_id.ids, datetime(2025, 8, 24), datetime(2025, 8, 30, 23, 59)
        )

        self.assertEqual(planning_hours_info_2nd_week[self.employee_bert.resource_id.id]['value'], 24)

    def test_compute_slots_data(self):
        """Test that planning.send wizard computes slot_ids and employee_ids correctly, including active_domain."""
        # Create two employees
        employee_a, employee_b = self.env['hr.employee'].create([
            {'name': 'Employee A'},
            {'name': 'Employee B'},
        ])

        # Create a planning role
        role_dev, role_other = self.env['planning.role'].create([
            {'name': 'Dev'},
            {'name': 'Tester'},
        ])

        # Create slots: one in range (role = Tester), one out of range
        slot_in_range = self.env['planning.slot'].create([
            {
                'start_datetime': datetime(2023, 11, 20, 9, 0),
                'end_datetime': datetime(2023, 11, 20, 16, 0),
                'resource_ids': employee_a.resource_id.ids,
                'role_id': role_other.id,
            },
            {
                'start_datetime': datetime(2023, 11, 19, 9, 0),
                'end_datetime': datetime(2023, 11, 19, 16, 0),
                'resource_ids': employee_b.resource_id.ids,
                'role_id': role_dev.id,
            },
        ])
        slot_in_range = slot_in_range[0]

        # Create wizard with a time window that only includes slot_in_range
        wizard = self.env['planning.send'].create({
            'start_datetime': datetime(2023, 11, 20, 8, 0),
            'end_datetime': datetime(2023, 11, 20, 17, 0),
        })
        wizard._compute_slots_data()

        # Wizard should only include slot_in_range
        self.assertIn(slot_in_range, wizard.slot_ids, "Wizard should include slots inside the range.")

        # Employee_ids should match employee of slot_in_range
        self.assertEqual(
            wizard.employee_ids,
            employee_a,
        )

        # Now test with active_domain filtering by role = Dev → should exclude slot_in_range
        wizard_ctx = wizard.with_context(active_domain=[('role_id', '=', role_dev.id)])
        wizard_ctx._compute_slots_data()
        self.assertFalse(
            wizard_ctx.slot_ids,
        )

    @freeze_time("2019-5-28 08:00:00")
    def test_user_assign_shift_multicompany(self):
        company = self.env['res.company'].create({"name": "Test company"})
        self.env.user.company_ids += company
        test_slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2019, 5, 28, 8, 0, 0),
            'end_datetime': datetime(2019, 5, 28, 17, 0, 0),
            'state': '2_published',
            'company_id': company.id,
        })
        with self.assertRaises(UserError):
            test_slot.with_company(company).action_self_assign()
        employee = self.env['hr.employee'].create({
            'name': 'odoobot',
            'work_email': 'odoobot@example.com',
            'tz': 'UTC',
            'create_date': '2015-01-01 00:00:00',
            'user_id': self.env.user.id,
            'company_id': company.id,
        })
        test_slot.with_company(company).action_self_assign()
        self.assertEqual(test_slot.employee_ids, employee)

    def test_avatar_card_archived_employee_info(self):
        self.authenticate("admin", "admin")
        employee = self.env["hr.employee"].create({
            "active": False,
            "name": "Test Emp",
        })
        data = self.make_jsonrpc_request(
            "/mail/store", {"fetch_params": [
                ["avatar_card", {"id": employee.resource_id.id, "model": "resource.resource"}]
            ]})
        self.assertEqual(data["resource.resource"][0]["name"], "Test Emp")

    def test_group_expand_resource_id_filters_by_department(self):
        """Test _group_expand_resource_id where one employee has slot and one doesn't, using department_id on resource."""

        department = self.env['hr.department'].create({
            'name': 'Test Department',
        })

        (self.employee_joseph + self.employee_bert).department_id = department

        self.env['planning.slot'].create({
            'resource_ids': self.employee_joseph.resource_id.ids,
            'start_datetime': datetime(2025, 4, 20, 8, 0),
            'end_datetime': datetime(2025, 4, 20, 17, 0),
        })

        domain = ['&', '|', ['department_id', 'ilike', 'Test Department'], ['resource_ids', '=', False], '&', ('start_datetime', '<', datetime(2025, 5, 3, 18, 30)), ('end_datetime', '>', datetime(2025, 4, 12, 18, 30))]

        expanded_resources = self.env['planning.slot'].with_context({'planning_expand_resource': True})._group_expand_resource_ids((self.employee_joseph + self.employee_bert).resource_id, domain)

        self.assertIn(self.employee_joseph.resource_id, expanded_resources, "Resource with planning slot should be returned.")
        self.assertIn(self.employee_bert.resource_id, expanded_resources, "Resource without slot should also be returned due to department.")

    def test_multi_shift_creation_excludes_non_working_days(self):
        """Ensure multi-shift creation automatically skips weekends (non-working days)."""
        flexible_calendar = self.flexible_calendar_40_8
        self.employee_bert.write({
            'resource_calendar_id': flexible_calendar.id,
        })
        slots = self.env['planning.slot'].with_context(multi_create=True).create([
            {
                'start_datetime': datetime(2025, 10, day, 9, 0, 0),
                'end_datetime': datetime(2025, 10, day, 17, 0, 0),
                'resource_ids': resource.ids,
                'template_id': self.template.id,
            } for day in range(5, 12) for resource in [self.resource_janice, self.resource_bert, self.resource_joseph]
        ])

        slots_janice = slots.filtered(lambda slot: slot.resource_ids == self.resource_janice)
        slots_bert = slots.filtered(lambda slot: slot.resource_ids == self.resource_bert)

        self.assertEqual(len(slots_janice), 5, "Standard schedule: shifts should be created only on working days.")
        self.assertEqual([slot.start_datetime.day for slot in slots_janice], [6, 7, 8, 9, 10], "Excluded 5 and 11 (Sat/Sun)")
        self.assertEqual(len(slots_bert), 5, "Flexible schedule: shifts should be created only on working days.")
        self.assertEqual([slot.start_datetime.day for slot in slots_bert], [5, 6, 7, 8, 9], "10 and 11 are non-working days.")

    def test_planning_send_action_check_emails(self):
        start_datetime = datetime(2024, 7, 1, 8, 0)
        end_datetime = datetime(2024, 7, 1, 17, 0)
        beth_shift, joseph_shift = self.env['planning.slot'].create([
            {'start_datetime': start_datetime, 'end_datetime': end_datetime, 'resource_ids': self.resource_bert.ids},
            {'start_datetime': start_datetime, 'end_datetime': end_datetime, 'resource_ids': self.resource_joseph.ids},
        ])
        self.assertEqual(beth_shift.state, '1_draft', 'The shift should be in draft state by default')
        self.assertEqual(joseph_shift.state, '1_draft', 'The shift should be in draft state by default')

        self.employee_bert.work_email = ''

        planning_send_wizard = self.env['planning.send'].create({
            'start_datetime': start_datetime,
            'end_datetime': end_datetime,
            'slot_ids': (beth_shift + joseph_shift).ids,
        })
        self.assertTrue(self.env['hr.employee'].has_access('write'))
        action = planning_send_wizard.action_check_emails()
        self.assertEqual(action['name'], 'No Email Address for Some Employees')
        self.assertEqual(action['type'], 'ir.actions.act_window', 'The action should open a form view to complete missing work email')

        # since the user has no access in edit to `hr.employee`, we will not send the planning to the employee without email set.
        self.assertFalse(self.env['hr.employee'].with_user(self.planning_manager_user).has_access('write'))
        action = planning_send_wizard.with_user(self.planning_manager_user).action_check_emails()
        self.assertEqual(action['type'], 'ir.actions.client', 'The action should return a notification')
        self.assertEqual(action['tag'], 'display_notification', 'The action should return a notification')
        self.assertDictEqual(action['params'], {
            'type': 'info',
            'message': "Shifts published — employees without a work email were skipped",
            'next': {'type': 'ir.actions.act_window_close'},
        })
        self.assertEqual(beth_shift.state, '1_draft', 'The shift should not be in published state after sending the planning since the employee set has no work_email and so no way to receive the planning')
        self.assertEqual(joseph_shift.state, '2_published', 'The shift should be in published state after sending the planning')

    @freeze_time("2026-02-27 08:00:00")
    def test_shift_template_updates_end_date(self):
        """checks that, despite an employee having a fixed schedule, the start and end hours of their shift
        will correspond to the applied shift template."""
        planning_role = self.env['planning.role'].create({
            'name': 'role for template',
        })
        self.employee_joseph.write({'default_planning_role_id': planning_role.id})
        template_slot = self.env['planning.slot.template'].create({
            'start_time': 11,
            'end_time': 19,
            'role_id': planning_role.id
        })
        with Form(self.env['planning.slot']) as slot:
            slot.role_id = planning_role
            slot.resource_ids = self.employee_joseph.resource_id
            slot.template_id = template_slot
            self.assertEqual(slot.start_datetime, datetime.now().date() + relativedelta(hour=11, minute=0, second=0))
            self.assertEqual(slot.end_datetime, datetime.now().date() + relativedelta(hour=19, minute=0, second=0))

    def test_planning_gantt_unavailabilities_flexible_employee(self):
        flexible_calendar = self.flexible_calendar_40_8
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'date_version': date(2019, 1, 1),
            'contract_date_start': date(2019, 1, 1),
            'contract_date_end': date(2019, 7, 29),
            'wage': 10,
            'tz': 'UTC',
            'resource_calendar_id': flexible_calendar.id,
        })

        unavailabilities = self.env['planning.slot']._gantt_unavailability(
            'resource_ids',
            [employee.resource_id.id],
            datetime(2019, 1, 1),
            datetime(2019, 1, 7),
            'week',
        )
        self.assertNotIn(employee.resource_id.id, unavailabilities)

    def test_only_add_assigned_materials_when_needed(self):
        material = self.env['resource.resource'].create({
            'name': "Material Resource",
            'resource_type': 'material',
            'assigned_employee_id': self.employee_bert.id,
        })
        slot = self.env['planning.slot'].with_context(import_file=True).create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 8, 0, 0),
            'resource_ids': self.resource_bert.ids,
        })
        self.assertNotIn(material, slot.resource_ids)

        copied_slot = slot.copy()
        self.assertNotIn(material, copied_slot.resource_ids)

        slot = self.env['planning.slot'].with_context(add_materials_assigned_to_employees=False).create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 8, 0, 0),
            'resource_ids': self.resource_bert.ids,
        })
        self.assertNotIn(material, slot.resource_ids)

        slot = self.env['planning.slot'].with_context(add_materials_assigned_to_employees=True).create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 8, 0, 0),
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(self.resource_bert + material, slot.resource_ids)

    def test_self_assign_and_unassign_from_shift_adds_and_removes_assigned_materials(self):
        self.env['res.config.settings'].create({'planning_employee_unavailabilities': 'unassign'}).execute()

        self.employee_bert.user_id = self.employee_bert._get_or_create_light_user()
        self.employee_joseph.user_id = self.employee_joseph._get_or_create_light_user()

        drill, sander, truck = self.env['resource.resource'].create([
            {
                'name': "Drill",
                'resource_type': 'material',
                'assigned_employee_id': self.employee_bert.id,
            },
            {
                'name': "Sander",
                'resource_type': 'material',
                'assigned_employee_id': self.employee_joseph.id,
            },
            {
                'name': "Truck",
                'resource_type': 'material',
            },
        ])
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime.now() + relativedelta(days=2),
            'end_datetime': datetime.now() + relativedelta(days=4),
            'state': '2_published',
            'resource_ids': (truck + self.resource_joseph + sander).ids,
        })
        self.assertEqual(truck + self.resource_joseph + sander, slot.resource_ids)
        slot.with_user(self.employee_joseph.user_id).action_switch_shift()

        slot.with_user(self.employee_bert.user_id).action_self_assign()
        self.assertEqual(truck + self.resource_bert + drill, slot.resource_ids, "Joseph and his assigned materials should be replaced by Bert and his assigned materials")

        slot.with_user(self.employee_bert.user_id).action_self_unassign()
        self.assertEqual(truck, slot.resource_ids)

    def test_planning_shift_template_company_domain(self):
        company_2 = self.env['res.company'].create({'name': 'Test company'})
        template_1, template_2, template_3 = self.env['planning.slot.template'].create([
            {'company_id': self.env.company.id},
            {'company_id': company_2.id},
            {'company_id': False},
        ])
        with Form(self.env['planning.slot']) as slot:
            # Check available templates on the current user company
            self.assertEqual(slot.company_id, self.env.company)
            self.assertIn(template_1.id, slot.template_autocomplete_ids.ids)
            self.assertNotIn(template_2.id, slot.template_autocomplete_ids.ids)
            self.assertIn(template_3.id, slot.template_autocomplete_ids.ids)
            # Check available templates on another company
            slot.company_id = company_2
            self.assertNotIn(template_1.id, slot.template_autocomplete_ids.ids)
            self.assertIn(template_2.id, slot.template_autocomplete_ids.ids)
            self.assertIn(template_3.id, slot.template_autocomplete_ids.ids)

    def test_set_shift_template_on_planning_slot_with_long_calendar_leave(self):
        """
        Test that applying a shift template on a planning slot when the
        resource calendar has a long leave.
        """
        self.env['resource.calendar.leaves'].create({
            'name': "Long Leaves",
            'calendar_id': self.resource_bert.calendar_id.id,
            'date_from': datetime(2019, 6, 5, 8, 0),
            'date_to': datetime(2023, 6, 24, 18, 0),
        })
        self.template.duration_days = 2

        self.slot.write({
            'resource_ids': self.resource_bert.ids,
            'template_id': self.template.id,
        })

        self.assertEqual(self.slot.start_datetime, datetime(2019, 6, 27, 11, 0))
        self.assertEqual(self.slot.end_datetime, datetime(2019, 6, 28, 14, 0))

    @freeze_time('2024-05-15 08:00:00')
    def test_unassigned_button_show_based_on_user(self):
        """
        Steps:
            1. Configure "Employee Unavailabilities" as "Unassign themselves from shifts".
            2. Create and publish a planning slot with a resource that has no user.
            3. Send the schedule email and verify the mail count and "I am unavailable" button.
            4. Create a user for the employee
            5. Repeat step 3.
        """
        self.env['res.config.settings'].create({
            'planning_employee_unavailabilities': 'unassign',
            'planning_self_unassign_days_before': 0,
        }).execute()

        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2024, 5, 15, 8, 0, 0),
            'end_datetime': datetime(2024, 5, 15, 17, 0, 0),
            'resource_ids': self.resource_bert.ids,
            'state': '2_published',
        })

        with self.mock_mail_gateway():
            slot.action_send()

        self.assertNotIn('I am unavailable', self._new_mails[0].body_html)
        self.assertEqual(len(self._new_mails), 1)

        self.employee_bert.user_id = self.employee_bert._get_or_create_light_user()
        with self.mock_mail_gateway():
            slot.action_send()
            self.assertIn('I am unavailable', self._new_mails[0].body_html)
            self.assertEqual(len(self._new_mails), 1)

    def test_planning_schedule_shift_from_side_panel_basic_case(self):
        """
        Test that the planning slot can be scheduled from the side panel, and that the correct values are set on the slot.
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        # Schedule a first slot with 5 allocated hours
        unscheduled_slot_1, unscheduled_slot_2, unscheduled_slot_3 = self.env['planning.slot'].create([
            {
                'name': 'Shift 1',
                'allocated_hours': 5,
                'start_datetime': False,
                'end_datetime': False,
            },
            {
                'name': 'Shift 2',
                'allocated_hours': 3,
                'start_datetime': False,
                'end_datetime': False,
            },
            {
                'name': 'Shift 3',
                'allocated_hours': 2,
                'start_datetime': False,
                'end_datetime': False,
            },
        ])
        # Schedule a first slot with 5 allocated hours
        unscheduled_slot_1.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({  # Week scale
            'start_datetime': '2012-02-19 22:00:00',  # Monday -> Monday
            'end_datetime': '2012-02-20 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(str(unscheduled_slot_1.start_datetime), '2012-02-20 08:00:00')
        self.assertEqual(str(unscheduled_slot_1.end_datetime), '2012-02-20 14:00:00')
        self.assertEqual(unscheduled_slot_1.allocated_hours, 5)

        # Schedule a second slot with 3 allocated hours the same day
        unscheduled_slot_2.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-19 22:00:00',  # Monday -> Monday
            'end_datetime': '2012-02-20 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(str(unscheduled_slot_2.start_datetime), '2012-02-20 14:00:00')
        self.assertEqual(str(unscheduled_slot_2.end_datetime), '2012-02-20 17:00:00')
        self.assertEqual(unscheduled_slot_2.allocated_hours, 3)

        # Schedule a third slot with 2 allocated hours the same day, should not be able to fit in the remaining time of the day
        unscheduled_slot_3.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-19 22:00:00',  # Try to schedule on Monday
            'end_datetime': '2012-02-20 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(str(unscheduled_slot_3.start_datetime), '2012-02-21 08:00:00', 'The slot should be scheduled the next day (Tuesday) as there is not enough time remaining on the first day to schedule it')
        self.assertEqual(str(unscheduled_slot_3.end_datetime), '2012-02-21 10:00:00', 'The slot should be scheduled the next day (Tuesday) as there is not enough time remaining on the first day to schedule it')
        self.assertEqual(unscheduled_slot_3.allocated_hours, 2)

    def test_planning_schedule_shift_from_side_panel_conflicts_handling(self):
        """
        Test that the planning slot can be scheduled from the side panel (and the shift was partially scheduled), and that the correct values are set on the slot despite conflicts.
        The slot can be scheduled into multiple slots, and a remaining slot can be created if there is not enough time to schedule the whole slot within the given time range.
        We can undo the action and the slot to schedule will be reverted to its previous state. The generated shifts that fill the period will also get removed in the process.
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        _dummy, _dummy, unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift 1',
                'start_datetime': '2012-02-21 08:00:00',  # Tuesday -> Wednesday
                'end_datetime': '2012-02-22 10:00:00',
                'resource_ids': self.resource_bert.ids,
            },
            {
                'name': 'Shift 2',
                'start_datetime': '2012-02-22 14:00:00',  # Wednesday -> Thursday
                'end_datetime': '2012-02-23 14:00:00',
                'resource_ids': self.resource_bert.ids,
            },
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 20,
                'start_datetime': False,
                'end_datetime': False,
            }
        ])
        # This slot should be scheduled between the two existing ones
        data = unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({  # Week scale
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(str(unscheduled_slot.start_datetime), '2012-02-22 10:00:00', 'The slot should be scheduled between the two existing slots (slot_1 and slot_2) on Wednesday, maximizing the allocated hours in this free period')
        self.assertEqual(str(unscheduled_slot.end_datetime), '2012-02-22 14:00:00', 'The slot should be scheduled between the two existing slots (slot_1 and slot_2) on Wednesday, maximizing the allocated hours in this free period')
        self.assertEqual(unscheduled_slot.allocated_hours, 3)
        self.assertEqual(unscheduled_slot.resource_ids, self.resource_bert, 'The slot should be assigned to the resource Bert after scheduling it from the side panel')

        # This slot should be scheduled after the two existing slots, until the end of the week
        remaining_slot = self.env['planning.slot'].search([
            ('name', '=', 'Shift to Schedule from Test'),
            ('start_datetime', '>=', '2012-02-22 14:00:00'),
            ('end_datetime', '<=', '2012-02-24 17:00:00'),
        ])
        self.assertEqual(str(remaining_slot.start_datetime), '2012-02-23 14:00:00', 'Another slot should have been created and scheduled from Thursday afternoon to Friday, with the remaining hours to schedule after scheduling the first part of the slot between the two existing slots')
        self.assertEqual(str(remaining_slot.end_datetime), '2012-02-24 17:00:00', 'Another slot should have been created and scheduled from Thursday afternoon to Friday, with the remaining hours to schedule after scheduling the first part of the slot between the two existing slots')
        self.assertEqual(remaining_slot.allocated_hours, 9)
        self.assertEqual(remaining_slot.resource_ids, self.resource_bert, 'The slot should be assigned to the resource Bert after scheduling it from the side panel')

        # There should be a remaining unscheduled slot for the hours that could not be scheduled
        remaining_unscheduled_slot = self.env['planning.slot'].search([
            ('name', '=', 'Shift to Schedule from Test'),
            ('start_datetime', '=', False),
            ('end_datetime', '=', False),
        ])
        self.assertEqual(remaining_unscheduled_slot.allocated_hours, 8, 'A remaining slot should be created for the unscheduled hours that could not be scheduled between the two existing slots')
        self.assertFalse(remaining_unscheduled_slot.resource_ids, 'The remaining unscheduled slot should not have any resources, as the slot to schedule had not any')

        # Check the returned data
        self.assertEqual(data['slots_assigned_ids'], (unscheduled_slot | remaining_slot | remaining_unscheduled_slot).ids, 'The slots assigned or created should be returned in the data of the assign_slot method')
        self.assertEqual(data['schedule_type'], 'partial', 'The schedule type should be partial as the slot was not fully scheduled within the given time range')
        slots_created_ids = data['undo_data']['slots_created_ids']
        self.assertEqual(slots_created_ids, (remaining_slot | remaining_unscheduled_slot).ids, 'New slots were created in the process of scheduling')
        undo_vals = data['undo_data']['undo_vals']
        self.assertEqual(undo_vals[unscheduled_slot.id]['start_datetime'], False, 'The undo values should contain the previous state of the slot with no start datetime')
        self.assertEqual(undo_vals[unscheduled_slot.id]['end_datetime'], False, 'The undo values should contain the previous state of the slot with no end datetime')
        self.assertEqual(undo_vals[unscheduled_slot.id]['allocated_hours'], 20, 'The undo values should contain the previous state of the slot with 20 allocated hours')
        self.assertFalse(undo_vals[unscheduled_slot.id]['resource_ids'], 'The undo values should contain the previous state of the slot with no resources assigned')

        # Undo the action
        undo_vals = {str(k): v for k, v in undo_vals.items()}  # We need to convert the keys (ids) into strings
        unscheduled_slot.undo_assign_slot(slots_created_ids, undo_vals)
        self.assertFalse(unscheduled_slot.start_datetime, 'The slot should be reverted to its previous state with no start datetime after undoing the action')
        self.assertFalse(unscheduled_slot.end_datetime, 'The slot should be reverted to its previous state with no end datetime after undoing the action')
        self.assertEqual(unscheduled_slot.allocated_hours, 20, 'The slot should be reverted to its previous state with 20 allocated hours after undoing the action')
        self.assertFalse(unscheduled_slot.resource_ids, 'The slot should be reverted to its previous state with no resources assigned')
        self.assertFalse(remaining_slot.exists(), 'The created slot that filled the given period should have been removed')
        self.assertFalse(remaining_unscheduled_slot.exists(), 'The created unscheduled slot containing the remaining hours to schedule should have been removed')

    def test_planning_schedule_shift_from_side_panel_could_not_schedule(self):
        """
        Test that when a planning slot is scheduled from the side panel but there is no time slot available to schedule it, the start and end datetime of the slot remain unchanged (False in this case as the slot is unscheduled).
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        _dummy, unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift 1',
                'start_datetime': '2012-02-24 08:00:00',  # Friday -> Friday
                'end_datetime': '2012-02-24 17:00:00',
                'resource_ids': self.resource_bert.ids,
            },
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 8,
                'start_datetime': False,
                'end_datetime': False,
            }
        ])
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-23 22:00:00',  # Try to schedule on Friday
            'end_datetime': '2012-02-24 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertFalse(unscheduled_slot.start_datetime, 'The slot should not be scheduled as there is not enough time to schedule it before the end of the week with the existing slot on Friday')
        self.assertFalse(unscheduled_slot.end_datetime, 'The slot should not be scheduled as there is not enough time to schedule it before the end of the week with the existing slot on Friday')
        self.assertEqual(unscheduled_slot.allocated_hours, 8, 'The allocated hours should remain unchanged even if the slot could not be scheduled')

    def test_planning_schedule_shift_from_side_panel_conflicts_handling_multi_resources(self):
        """
        Test that when a planning slot is scheduled from the side panel on multiple resources, we take into account the availabilities of all resources assigned to the slot.
        """
        (self.employee_bert + self.employee_joseph + self.employee_janice).resource_calendar_id = self.company_calendar
        _dummy, _dummy, unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift Bert',
                'start_datetime': '2012-02-21 08:00:00',  # Tuesday -> Wednesday
                'end_datetime': '2012-02-22 10:00:00',
                'resource_ids': self.resource_bert.ids,
            },
            {
                'name': 'Shift Joseph',
                'start_datetime': '2012-02-22 14:00:00',  # Wednesday -> Thursday
                'end_datetime': '2012-02-23 14:00:00',
                'resource_ids': self.resource_joseph.ids,
            },
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 3,
                'start_datetime': False,
                'end_datetime': False,
            }
        ])
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({  # Week scale
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': (self.resource_bert + self.resource_joseph).ids,
        })
        self.assertEqual(str(unscheduled_slot.start_datetime), '2012-02-22 10:00:00', 'The slot should be scheduled between the two existing slots (slot_1 and slot_2) on Wednesday, maximizing the allocated hours in this free period')
        self.assertEqual(str(unscheduled_slot.end_datetime), '2012-02-22 14:00:00', 'The slot should be scheduled between the two existing slots (slot_1 and slot_2) on Wednesday, maximizing the allocated hours in this free period')
        self.assertEqual(unscheduled_slot.allocated_hours, 3)

    def test_planning_schedule_shift_from_side_panel_resources_assignation(self):
        """
        Test that when planning a slot having multiple resources from the side panel, we update the resource_ids of the slot with the following logic:
        Let's say the shift to be scheduled is assigned to resources A and B
        If dragged and dropped into "Open Shifts" -> leave it assigned to A and B
        If dragged and dropped into resource A -> leave it assigned to A and B
        If dragged and dropped into resource C -> unassign A and B, and assign to C
        """
        (self.employee_bert + self.employee_joseph + self.employee_janice).resource_calendar_id = self.company_calendar
        unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 3,
                'start_datetime': False,
                'end_datetime': False,
                'resource_ids': (self.resource_bert + self.resource_joseph).ids,
            }
        ])
        # Schedule on open shift
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': False,
        })
        self.assertEqual(unscheduled_slot.resource_ids, self.resource_bert + self.resource_joseph, 'When scheduling on open shifts, we should not change the assigned resources')
        unscheduled_slot.start_datetime = False
        unscheduled_slot.end_datetime = False
        unscheduled_slot.allocated_hours = 3
        # Schedule on resource Bert
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(unscheduled_slot.resource_ids, self.resource_bert + self.resource_joseph, 'When scheduling on resource Bert, we should not change the assigned resources as the slot is already assigned to Bert and scheduling on Bert should not unassign other assigned resources')
        unscheduled_slot.start_datetime = False
        unscheduled_slot.end_datetime = False
        unscheduled_slot.allocated_hours = 3
        # Schedule on resource Janice
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': self.resource_janice.ids,
        })
        self.assertEqual(unscheduled_slot.resource_ids, self.resource_janice, 'When scheduling on resource Janice, we should unassign previous resources and only assign it to Janice')

    def test_planning_schedule_shift_from_side_panel_with_leaves(self):
        """
        Test that when scheduling a shift from the side panel, if there are leaves on the resource calendar during the time range we want to schedule the shift, we take into account the leave and schedule the shift accordingly
        (either by splitting the shift into multiple shifts around the leave, or by scheduling the shift after the leave if there is not enough time to schedule it before the leave).
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        self.env['resource.calendar.leaves'].create({
            'name': 'Dentist Appointment',
            'calendar_id': self.employee_bert.resource_calendar_id.id,
            'date_from': '2012-02-22 08:00:00',  # Off on Wednesday
            'date_to': '2012-02-22 17:00:00',
        })
        unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 16,
                'start_datetime': False,
                'end_datetime': False,
            }
        ])
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({  # Week scale
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        # The first part of the shift should be scheduled before the leave, on Tuesday
        first_scheduled_slot = self.env['planning.slot'].search([
            ('name', '=', 'Shift to Schedule from Test'),
            ('start_datetime', '=', '2012-02-21 08:00:00'),
            ('end_datetime', '=', '2012-02-21 17:00:00'),
        ])
        self.assertEqual(first_scheduled_slot.allocated_hours, 8)
        # The second part of the shift should be scheduled after the leave, on Thursday
        second_scheduled_slot = self.env['planning.slot'].search([
            ('name', '=', 'Shift to Schedule from Test'),
            ('start_datetime', '=', '2012-02-23 06:00:00'),
            ('end_datetime', '=', '2012-02-23 15:00:00'),
        ])
        self.assertEqual(second_scheduled_slot.allocated_hours, 8)

    def test_planning_schedule_shift_from_side_panel_no_allocated_hours(self):
        """
        Test that when scheduling a shift from the side panel with no allocated hours, the shift will be scheduled with a default allocated hours value based on the scale of the view.
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 0,
                'start_datetime': False,
                'end_datetime': False,
            }
        ])
        unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00', scale='week').assign_slot({
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(str(unscheduled_slot.start_datetime), '2012-02-21 08:00:00', 'The slot should be scheduled on Tuesday with 8 allocated hours')
        self.assertEqual(str(unscheduled_slot.end_datetime), '2012-02-21 17:00:00', 'The slot should be scheduled on Tuesday with 8 allocated hours')
        self.assertEqual(unscheduled_slot.allocated_hours, 8, 'The allocated hours should be set to the default value based on the scale of the view (8 hours for week scale)')

    def test_gantt_progress_bar_grouped_by_role_with_flexible_resource(self):
        """Test the Gantt progress bar when grouping by a role with a flexible resource."""
        self.slot.write({
            'role_id': self.flex_role.id,
            'start_datetime': datetime(2026, 7, 20, 12, 0),
            'end_datetime': datetime(2026, 7, 21, 2, 0),
        })

        self.assertTrue(self.flex_role.resource_ids)

        result = self.env['planning.slot'].get_gantt_data(
            domain=[
                ('start_datetime', '<', '2026-07-20 18:30:00'),
                ('end_datetime', '>', '2026-07-19 18:30:00'),
            ],
            groupby=['role_id'],
            read_specification={'display_name': {}},
            start_date='2026-07-19 18:30:00',
            stop_date='2026-07-20 18:30:00',
            progress_bar_fields=['role_id'],
        )
        progress = result['progress_bars']['role_id']

        self.assertIn(self.flex_role.id, progress)
        self.assertEqual(progress[self.flex_role.id]['value'], 0.0)
        self.assertFalse(progress[self.flex_role.id]['all_group_by_resources_fully_flexible'])

    @freeze_time('2024-05-15 08:00:00')
    def test_assigned_button_show_based_on_user(self):
        """
        Steps:
            1. Create and publish a planning slot.
            2. Create a user for the Bert employee.
            3. Send the schedule email and verify the Assign me this shift button is present.
            4. Check that the users email (Bert) contains the Assign me this shift button.
            5. Check that the employee email (joseph) does not contain the Assign me this shift button.
        """
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2024, 5, 15, 8, 0, 0),
            'end_datetime': datetime(2024, 5, 15, 17, 0, 0),
        })

        self.employee_bert.user_id = self.employee_bert._get_or_create_light_user()
        with self.mock_mail_gateway():
            slot.action_send()

        bert_mail = self._new_mails.filtered(lambda m: m.email_to == self.employee_bert.work_email)
        joseph_mail = self._new_mails.filtered(lambda m: m.email_to == self.employee_joseph.work_email)

        self.assertEqual(len(bert_mail), 1)
        self.assertIn('Assign me this shift', bert_mail.body_html)

        self.assertEqual(len(joseph_mail), 1)
        self.assertNotIn('Assign me this shift', joseph_mail.body_html)

    def test_planning_email_single_attachment_with_multiple_resources(self):
        """
            - create shift with two resources
            - send shift
            - check mails and verify single attachment per shift
        """
        shift = self.env['planning.slot'].create({
            'name': 'Morning Shift',
            'start_datetime': '2026-05-29 08:00:00',
            'end_datetime': '2026-05-29 16:00:00',
            'resource_ids': (self.resource_joseph + self.resource_bert).ids,
        })

        with self.mock_mail_gateway():
            shift.action_send()

        self.assertEqual(len(self._new_mails), 2,
            "Both resource emails should be sent.")
        self.assertEqual(len(self._new_mails.attachment_ids), 1,
            "Attachment should not be duplicated.")

    def test_planning_schedule_shift_from_side_panel_undo_action(self):
        """
        Test that when scheduling a shift from the side panel (and the shift was fully scheduled), we can undo the action and the slot to schedule will be reverted to its previous state.
        """
        self.employee_bert.resource_calendar_id = self.company_calendar
        unscheduled_slot = self.env['planning.slot'].create([
            {
                'name': 'Shift to Schedule from Test',
                'allocated_hours': 8,
                'start_datetime': False,
                'end_datetime': False,
                'company_id': self.env.company.id,
            }
        ])
        data = unscheduled_slot.with_context(default_end_datetime='2012-02-24 17:00:00').assign_slot({
            'start_datetime': '2012-02-20 22:00:00',  # Try to schedule on Tuesday
            'end_datetime': '2012-02-21 22:00:00',
            'resource_ids': self.resource_bert.ids,
        })
        self.assertEqual(str(unscheduled_slot.start_datetime), '2012-02-21 08:00:00', 'The slot should be scheduled on Tuesday with 8 allocated hours')
        self.assertEqual(str(unscheduled_slot.end_datetime), '2012-02-21 17:00:00', 'The slot should be scheduled on Tuesday with 8 allocated hours')
        self.assertEqual(unscheduled_slot.allocated_hours, 8, 'The allocated hours should be set to the default value based on the scale of the view (8 hours for week scale)')
        self.assertEqual(unscheduled_slot.resource_ids, self.resource_bert, 'The slot should be assigned to the resource Bert after scheduling it from the side panel')

        self.assertEqual(data['slots_assigned_ids'], unscheduled_slot.ids, 'The slot assigned should be returned in the data of the assign_slot method')
        self.assertEqual(data['schedule_type'], 'full', 'The schedule type should be full as the slot was fully scheduled within the given time range')
        slots_created_ids = data['undo_data']['slots_created_ids']
        self.assertFalse(slots_created_ids, 'No new slots should be created as the slot was fully scheduled within the given time range')
        undo_vals = data['undo_data']['undo_vals']
        self.assertEqual(undo_vals[unscheduled_slot.id]['start_datetime'], False, 'The undo values should contain the previous state of the slot with no start datetime')
        self.assertEqual(undo_vals[unscheduled_slot.id]['end_datetime'], False, 'The undo values should contain the previous state of the slot with no end datetime')
        self.assertEqual(undo_vals[unscheduled_slot.id]['allocated_hours'], 8, 'The undo values should contain the previous state of the slot with 8 allocated hours')
        self.assertFalse(undo_vals[unscheduled_slot.id]['resource_ids'], 'The undo values should contain the previous state of the slot with no resources assigned')
        self.assertEqual(undo_vals[unscheduled_slot.id]['company_id'], self.env.company.id, 'The undo values should contain the previous state of the slot with the current company assigned')

        # Undo the action
        undo_vals = {str(k): v for k, v in undo_vals.items()}  # We need to convert the keys (ids) into strings
        unscheduled_slot.undo_assign_slot(slots_created_ids, undo_vals)
        self.assertFalse(unscheduled_slot.start_datetime, 'The slot should be reverted to its previous state with no start datetime after undoing the action')
        self.assertFalse(unscheduled_slot.end_datetime, 'The slot should be reverted to its previous state with no end datetime after undoing the action')
        self.assertEqual(unscheduled_slot.allocated_hours, 8, 'The slot should be reverted to its previous state with 8 allocated hours after undoing the action')
        self.assertFalse(unscheduled_slot.resource_ids, 'The slot should be reverted to its previous state with no resources assigned')
        self.assertEqual(unscheduled_slot.company_id, self.env.company, 'The slot should be reverted to its previous state with the current company assigned')
