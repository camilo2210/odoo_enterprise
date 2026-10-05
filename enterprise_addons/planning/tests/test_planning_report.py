# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.planning.tests.common import TestCommonPlanning
from odoo.addons.resource.models.utils import get_light_color


@tagged("post_install", "-at_install")
class TestPlanningReport(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        cls.setUpDates()
        cls.setUpCalendars()

        cls.planning_role = cls.env["planning.role"].create({
            "name": "Developer",
        })

        cls.slot_1, cls.slot_2 = cls.env["planning.slot"].create([{
            "start_datetime": "2024-01-01 08:00:00",
            "end_datetime": "2024-01-01 17:00:00",
            "resource_ids": [cls.resource_joseph.id],
            "role_id": cls.planning_role.id,
        }, {
            "start_datetime": "2024-01-02 08:00:00",
            "end_datetime": "2024-01-02 17:00:00",
            "resource_ids": [cls.resource_bert.id],
            "role_id": cls.planning_role.id,
        }])

    def test_planning_report_create_action_blocked(self):
        """Test that adding the planning report to the print menu is blocked."""
        planning_report = self.env.ref("planning.report_planning_slot")
        with self.assertRaises(UserError) as capture:
            planning_report.create_action()

        self.assertEqual(
            capture.exception.args[0],
            "The Planning report cannot be added to the print menu. "
            "Please use the Print action available in the Planning calendar and Gantt views."
        )

    def test_planning_report_without_data_raises_error(self):
        """Test that printing from list/form view (without required context) raises UserError.

        This simulates the scenario where a user already added the report to the Print
        menu (before the fix) and tries to print from list/form view.
        """
        with self.assertRaises(UserError) as capture:
            self.env["ir.actions.report"].with_context(force_report_rendering=True)._render_qweb_pdf(
                "planning.report_planning_slot", res_ids=[self.slot_1.id, self.slot_2.id]
            )

        self.assertEqual(
            capture.exception.args[0],
            "The Planning report cannot be printed from here. "
            "Please use the Print action available in the Planning calendar and Gantt views."
        )

    def test_planning_report_with_proper_data_works(self):
        """Test that the correct workflow (Print button in calendar view) still works."""
        result = self.env["planning.slot"].action_print_plannings(
            "2024-01-01 00:00:00",
            "2024-01-07 23:59:59",
            ["resource_ids"],
            [("id", "in", [self.slot_1.id, self.slot_2.id])],
        )

        self.assertEqual(result.get("type"), "ir.actions.report")
        self.assertDictEqual(
            {key: key in result.get("data", {}) for key in ("weeks", "group_by_slots_per_day_per_week", "group_by_name_by_id")},
            {"weeks": True, "group_by_slots_per_day_per_week": True, "group_by_name_by_id": True},
        )

    def test_print_planning(self):
        """
            In this test, we make sure that the split works well for:
            1- slots starting before the week first day: we split the pill, and eliminate the part before the week start day
            2- slots ending before the week end day: we split the pill, and eliminate the part after the week end day
            3- the remaining part (inside the week) is splitted into many pills (pill per day), allocated hours, start_datetime and end_datetime
               are computed for each pill based on the resource availabilities
        """
        flexEmployee, standardEmployee = self.env['hr.employee'].create([{
            'name': 'Flex Employee',
            'tz': 'UTC',
        }, {
            'name': 'Standard Employee',
            'tz': 'UTC',
        }])

        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 40,
            'hours_per_day': 8,
        })
        flexEmployee.write({
            'resource_calendar_id': flexible_calendar.id,
        })
        standardEmployee.resource_id.calendar_id = self.company_calendar
        slots_count = self.env['planning.slot'].search_count([])

        # the diff between start and end is exactly 6 days
        self.env.user.tz = 'UTC'
        # Case 1: Create a planning slot on non-working days with a specific employee resource
        slot1, slot2, slot3 = self.env['planning.slot'].with_context(tz='UTC').create([{
            'resource_ids': [flexEmployee.resource_id.id],
            'start_datetime': datetime(2025, 5, 16, 8, 0, 0),
            'end_datetime': datetime(2025, 5, 20, 17, 0, 0),
        }, {
            'resource_ids': [standardEmployee.resource_id.id],
            'start_datetime': datetime(2025, 5, 21, 8, 0, 0),
            'end_datetime': datetime(2025, 5, 26, 17, 0, 0),
        }, {
            'start_datetime': datetime(2025, 5, 16, 8, 0, 0),
            'end_datetime': datetime(2025, 5, 19, 17, 0, 0),
        }])

        slots = slot1 | slot2 | slot3
        current_slots_count = self.env['planning.slot'].search_count([])
        self.assertEqual(current_slots_count, len(slots) + slots_count, "3 slots should be created")

        field_involved_in_fake_pill_creating_and_updating = slots._print_planning_get_fields_to_copy()

        def get_slots_values(slots):
            values = {}
            for slot in slots:
                values[slot.id] = {
                    field: slot[field]
                    for field in field_involved_in_fake_pill_creating_and_updating
                }

            return values

        original_values = get_slots_values(slots)

        action = self.env['planning.slot'].with_context(discard_logo_check=True).action_print_plannings(
            date_start='2025-05-18 00:00:00',
            date_end='2025-05-24 23:59:59',
            group_bys=['resource_ids'],
            domain=[['start_datetime', '<', '2025-05-25 00:00:00'], ['end_datetime', '>', '2025-05-18 00:00:00']]
        )

        # make sure fake slots are not created in db
        self.assertEqual(current_slots_count, self.env['planning.slot'].search_count([]), "no additional slots should be created")
        all_slots = self.env['planning.slot'].search([['start_datetime', '<', '2025-05-25 00:00:00'], ['end_datetime', '>', '2025-05-18 00:00:00']])

        # make sure existing slots are not updated when manipulating fake slots
        slots_after_printing = all_slots & slots
        self.assertDictEqual(original_values, get_slots_values(slots_after_printing))

        # OPEN SHIFTS: from 18 to 19, other are eliminated because they're outside the week period,
        # each slot is from 00:00 to 23:59 (because there is no calendar to follow) and has 8 allocated hours following the company work schedule
        # except day 19 as it takes the slot end_datetime
        self.assertEqual(len(action['data']['group_by_slots_per_day_per_week']), 1, "one week")
        self.assertEqual(len(action['data']['group_by_slots_per_day_per_week'][0]), 3)

        # resources should be sorted as (False, display named in non DESC order)
        self.assertEqual(action['data']['group_by_slots_per_day_per_week'][0][0], (False, {
            'Sunday 18': [
                {'title': '12:00 AM – 11:59 PM', 'style': 'background-color: #80c3c2;'}
            ],
            'Monday 19': [
                {'title': '12:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'}
            ],
        }))

        # FLEX EMPLOYEE: from 18 to 20, other are eliminated because they're outside the week period,
        # each slot is from 00:00 to 23:59 and has 8 allocated hours following the 40h/week
        # except day 20 as it takes the slot end_datetime

        self.assertEqual(action['data']['group_by_slots_per_day_per_week'][0][1][0], flexEmployee.resource_id.id)
        self.assertDictEqual(action['data']['group_by_slots_per_day_per_week'][0][1][1], {
            'Sunday 18': [
                {'title': '12:00 AM – 11:59 PM', 'style': 'background-color: #80c3c2;'}
            ],
            'Monday 19': [
                {'title': '12:00 AM – 11:59 PM', 'style': 'background-color: #80c3c2;'}
            ],
            'Tuesday 20': [
                {'title': '12:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'}
            ],
        })

        # STANDARD EMPLOYEE: from 22 to 23, other are eliminated because they're outside the week period and 24 is part of the weekend
        # each slot is from 08:00 to 17:00 and has 8 allocated hours, except day 22 (from 6 to 15) following exaclty company_calendar
        self.assertEqual(action['data']['group_by_slots_per_day_per_week'][0][2][0], standardEmployee.resource_id.id)
        self.assertDictEqual(action['data']['group_by_slots_per_day_per_week'][0][2][1], {
            'Wednesday 21': [
                {'title': '08:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'}
            ],
            'Thursday 22': [
                {'title': '06:00 AM – 03:00 PM', 'style': 'background-color: #80c3c2;'}
            ],
            'Friday 23': [
                {'title': '08:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'}
            ]
        })

        self.assertEqual(action['data']['weeks'][0], (0, [
            'Sunday 18',
            'Monday 19',
            'Tuesday 20',
            'Wednesday 21',
            'Thursday 22',
            'Friday 23',
            'Saturday 24',
        ], 'Week 21, May 18 - May 24'))

    def test_print_planning_group_by_role(self):
        """
        Test that printing the planning report grouped by a non-resource field (e.g., role_id)
        does not crash. This explicitly tests:
        1. Multi-day shifts can still correctly extract the resource for time-splitting.
        2. Empty/False groups (unassigned roles) are sorted and named without throwing TypeErrors.
        """
        self.env.user.tz = 'UTC'
        self.slot_1.write({
            'start_datetime': "2024-01-01 08:00:00",
            'end_datetime': "2024-01-02 17:00:00",
        })
        self.slot_2.write({
            'start_datetime': "2024-01-03 08:00:00",
            'end_datetime': "2024-01-04 17:00:00",
            'role_id': False,
        })

        action = self.env['planning.slot'].with_context(discard_logo_check=True).action_print_plannings(
            date_start='2024-01-01 00:00:00',
            date_end='2024-01-07 23:59:59',
            group_bys=['role_id'],
            domain=[('id', 'in', (self.slot_1 | self.slot_2).ids)]
        )
        self.assertTrue(action, "Action should successfully return a report dictionary")

        data = action.get('data', {})
        weekly_data = data.get('group_by_slots_per_day_per_week', {})
        groups = weekly_data.get(0, [])
        self.assertEqual(len(groups), 2, "There should be exactly 2 groups: The Developer role, and the Undefined role")

        group_ids = [g[0] for g in groups]
        self.assertIn(self.planning_role.id, group_ids, "The Developer role ID should be a group key")
        self.assertIn(False, group_ids, "The unassigned (False) role should safely be a group key")

        names_dict = data.get('group_by_name_by_id', {})
        self.assertEqual(names_dict.get(str(self.planning_role.id)), 'Developer')

        role_string = self.env['planning.slot'].fields_get(['role_id'])['role_id']['string']
        expected_undefined_string = "Undefined %s" % role_string
        self.assertEqual(names_dict.get('false'), expected_undefined_string)

    def test_order_of_planning_slots_in_report(self):
        self.employee_bert.resource_id.calendar_id = self.company_calendar
        self.env.user.tz = 'UTC'
        self.maxDiff = None
        slots = self.env['planning.slot'].with_context(tz='UTC').create([{
            'resource_ids': [self.employee_bert.resource_id.id],
            'start_datetime': datetime(2025, 5, 20, 8, 0, 0),
            'end_datetime': datetime(2025, 5, 20, 9, 0, 0),
        }, {
            'resource_ids': [self.employee_bert.resource_id.id],
            'start_datetime': datetime(2025, 5, 20, 9, 0, 0),
            'end_datetime': datetime(2025, 5, 20, 10, 0, 0),
        }, {
            'resource_ids': [self.employee_bert.resource_id.id],
            'start_datetime': datetime(2025, 5, 20, 10, 0, 0),
            'end_datetime': datetime(2025, 5, 22, 17, 0, 0),
        }, {
            'resource_ids': [self.employee_bert.resource_id.id],
            'start_datetime': datetime(2025, 5, 21, 1, 0, 0),
            'end_datetime': datetime(2025, 5, 21, 17, 0, 0),
        }, {
            'resource_ids': [self.employee_bert.resource_id.id],
            'start_datetime': datetime(2025, 5, 20, 8, 0, 0),
            'end_datetime': datetime(2025, 5, 20, 9, 0, 0),
            'role_id': self.planning_role.id,
        }])

        action = self.env['planning.slot'].with_context(discard_logo_check=True).action_print_plannings(
            date_start='2025-05-18 00:00:00',
            date_end='2025-05-24 23:59:59',
            group_bys=['resource_ids'],
            domain=[['start_datetime', '<', '2025-05-25 00:00:00'], ['end_datetime', '>', '2025-05-18 00:00:00']]
        )

        """
        Expected slots
        +---------------------------+---------------------------+---------------------------+
        | Tuesday 20                | Wednesday 21              | Thursday 22               |
        +---------------------------+---------------------------+---------------------------+
        | Slot 1                    | Slot 3                    | Slot 3                    |
        | 8:00 AM – 9:00 AM         | 8:00 AM – 5:00 PM         | 6:00 AM – 5:00 PM         |
        +---------------------------+---------------------------+---------------------------+
        | Slot 5 (flex role)        | Slot 4                    |                           |
        | 8:00 AM – 9:00 AM         | 1:00 AM – 5:00 PM         |                           |
        +---------------------------+---------------------------+---------------------------+
        | Slot 2                    |                           |                           |
        | 9:00 AM – 10:00 AM        |                           |                           |
        +---------------------------+---------------------------+---------------------------+
        | Slot 3                    |                           |                           |
        | 10:00 AM – 5:00 PM        |                           |                           |
        +---------------------------+---------------------------+---------------------------+
        """

        weekly_slot_data = dict(action['data']['group_by_slots_per_day_per_week'][0][0][1])
        slot5_color = get_light_color(slots[4].role_id.color, 0.5, not slots[4].resource_ids)
        self.assertDictEqual(weekly_slot_data, {
            # All the shits follow time order
            'Tuesday 20': [
                {'title': '08:00 AM – 09:00 AM', 'style': 'background-color: #80c3c2;'},
                {'title': '08:00 AM – 09:00 AM Developer', 'style': f'background-color: {slot5_color};'},
                {'title': '09:00 AM – 10:00 AM', 'style': 'background-color: #80c3c2;'},
                {'title': '10:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'},
            ],
            'Wednesday 21': [
                {'title': '08:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'},
                {'title': '01:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'},
            ],
            'Thursday 22': [
                {'title': '06:00 AM – 05:00 PM', 'style': 'background-color: #80c3c2;'},
            ],
        })
