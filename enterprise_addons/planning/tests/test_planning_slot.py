# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

from .common import TestPlanningContractCommon
from odoo.tests import tagged, new_test_user
from odoo.tools.intervals import Intervals


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningContract(TestPlanningContractCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # This contract ends at the 15th of the month
        cls.employee_bert.version_id.write({  # Fixed term contract
            'contract_date_end': datetime.strptime('2015-11-15', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'date_version': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'name': 'First CDD Contract for Jules',
            'resource_calendar_id': cls.calendar_40h.id,
            'wage': 5000.0,
        })
        cls.contract_cdd = cls.employee_bert.version_id

        # This contract starts the next day
        cls.contract_cdi = cls.employee_bert.create_version({
            'contract_date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_end': False,
            'date_version': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'name': 'Contract for Jules',
            'resource_calendar_id': cls.calendar_35h.id,
            'wage': 5000.0,
        })

        # Shared flexible calendars, reused across the flexible-schedule tests below instead of
        # each one creating its own.
        cls.fully_flexible_calendar, cls.flexible_calendar_30_6 = cls.env['resource.calendar'].create([
            {
                'name': 'Fully Flexible Calendar',
                'calendar_type': 'undefined',
                'attendance_ids': [],
            },
            {
                'name': 'Flexible Calendar 30h/week',
                'calendar_type': 'undefined',
                'attendance_ids': [],
                'hours_per_week': 30,
                'hours_per_day': 6,
            },
        ])

    def test_employee_contract_validity_per_period(self):
        start = datetime(2015, 11, 8, 00, 00, 00, tzinfo=UTC)
        end = datetime(2015, 11, 21, 23, 59, 59, tzinfo=UTC)
        calendars_validity_within_period = self.resource_bert._get_calendars_validity_within_period(start, end, default_company=self.employee_bert.company_id)
        tz = ZoneInfo(self.employee_bert.tz)

        self.assertEqual(len(calendars_validity_within_period[self.resource_bert.id]), 2, "There should exist 2 calendars within the period")
        interval_calendar_40h = Intervals([(
            start,
            datetime.combine(self.contract_cdd.date_end, datetime.max.time(), tzinfo=tz),
            self.env['resource.calendar.attendance']
        )])
        interval_calendar_35h = Intervals([(
            datetime.combine(self.contract_cdi.date_start, datetime.min.time(), tzinfo=tz),
            end,
            self.env['resource.calendar.attendance']
        )])
        computed_interval_40h = calendars_validity_within_period[self.resource_bert.id][self.calendar_40h]
        computed_interval_35h = calendars_validity_within_period[self.resource_bert.id][self.calendar_35h]
        self.assertFalse(computed_interval_40h - interval_calendar_40h, "The interval of validity for the 40h calendar must be from 2015-11-16 to 2015-11-21, not more")
        self.assertFalse(interval_calendar_40h - computed_interval_40h, "The interval of validity for the 40h calendar must be from 2015-11-16 to 2015-11-21, not less")
        self.assertFalse(computed_interval_35h - interval_calendar_35h, "The interval of validity for the 35h calendar must be from 2015-11-08 to 2015-11-15, not more")
        self.assertFalse(interval_calendar_35h - computed_interval_35h, "The interval of validity for the 35h calendar must be from 2015-11-08 to 2015-11-15, not less")

    def test_employee_work_intervals(self):
        start = datetime(2015, 11, 8, 00, 00, 00, tzinfo=UTC)
        end = datetime(2015, 11, 21, 23, 59, 59, tzinfo=UTC)
        work_intervals, _ = self.resource_bert._get_valid_work_intervals(start, end)
        sum_work_intervals = sum(
            (stop - start).total_seconds() / 3600
            for start, stop, _resource in work_intervals[self.resource_bert.id]
        )
        self.assertEqual(75, sum_work_intervals, "Sum of the work intervals for the employee Jules should be 40h+35h = 75h")

    def test_employee_work_planning_hours_info(self):
        planning_hours_info = self.env['planning.slot']._gantt_progress_bar(
            'resource_ids', self.resource_bert.ids, datetime(2015, 11, 8), datetime(2015, 11, 21, 23, 59, 59)
        )
        self.assertEqual(75, planning_hours_info[self.resource_bert.id]['max_value'], "Work hours for the employee Jules should be 40h+35h = 75h")

    def test_gantt_progress_bar_work_intervals_timezone(self):
        self.resource_bert.tz = 'Europe/Brussels'
        self.resource_bert.calendar_id = self.calendar_40h

        self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 16, 17, 0, 0),
            'resource_ids': self.resource_bert.ids,
        })
        domain = [['start_datetime', '<', datetime(2015, 12, 18, 0, 0, 0)], ['end_datetime', '>', datetime(2015, 12, 15, 0, 0, 0)]]
        planning_hours_info = self.env['planning.slot']._get_gantt_planning_data(domain, datetime(2015, 12, 16), datetime(2015, 12, 17))

        res_intervals = [
            (datetime(2015, 12, 16, 7, 0, 0).replace(tzinfo=UTC), datetime(2015, 12, 16, 11, 0, 0).replace(tzinfo=UTC)),
            (datetime(2015, 12, 16, 12, 0, 0).replace(tzinfo=UTC), datetime(2015, 12, 16, 16, 0, 0).replace(tzinfo=UTC))
        ]
        self.assertEqual(planning_hours_info['work_intervals'][self.resource_bert.id], res_intervals, "work_intervals should be in UTC")

    def test_creation_recurrencing_planning_without_employee_contract_access(self):
        """
            The creation of recurring schedules requires information on contracts.
            The goal is to test whether a user who is "Administrator" for Planning
            but has no Employee and Contract rights can use this flow.
        """
        planning_value = {
            'name': 'Test planning',
            'start_datetime': datetime(2015, 11, 8, 00, 00, 00),
            'end_datetime': datetime(2015, 11, 21, 23, 59, 59),
            'resource_ids': self.resource_bert.ids,
            'repeat': True,
            'repeat_type': 'x_times',
            'repeat_number': 2,
            'repeat_interval': 1,
            'repeat_unit': 'month',
        }
        user_admin = new_test_user(
            self.env, "User Admin",
            groups='planning.group_planning_manager,hr.group_hr_manager,hr.group_hr_manager'
        )
        user_without_contract = new_test_user(
            self.env, "User Without Contract",
            groups='planning.group_planning_manager,hr.group_hr_manager'
        )
        user_without_employee = new_test_user(
            self.env, "User Without Employee",
            groups='planning.group_planning_manager'
        )
        self.env['planning.slot'].with_user(user_admin).create(planning_value)
        self.env.invalidate_all()
        self.env['planning.slot'].with_user(user_without_contract).create(planning_value)
        self.env.invalidate_all()
        self.env['planning.slot'].with_user(user_without_employee).create(planning_value)

    def test_allocated_hours_of_slot_with_flexible_contract(self):
        """
            When a flexible or fully flexible employee plan a slot outside the period of
            the contract, the pre-computed allocated hours should be 0 hours.
            Additionally, apply the test for a flexible contract with no end date.
        """

        # 1) Set a fully flexible contract for an employee
        fully_flexible_calendar = self.fully_flexible_calendar
        self.employee_joseph.version_id.write({
            'contract_date_end': datetime.strptime('2015-12-16', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'date_version': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'name': 'Fully flex contract for Joseph',
            'resource_calendar_id': fully_flexible_calendar.id,
            'wage': 5000.0,
        })

        # Create a slot outside the contract period
        slot_outside = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 17, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 12, 0, 0),
            'resource_ids': self.resource_joseph.ids,
        })
        self.assertEqual(slot_outside.allocated_hours, 0, "The allocated hours should be 0 for a slot outside the contract period of a fully flexible employee")

        # Create a slot inside the contract period
        slot_inside = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 16, 1, 0, 0),
            'end_datetime': datetime(2015, 12, 16, 12, 0, 0),
            'resource_ids': self.resource_joseph.ids,
        })
        self.assertEqual(slot_inside.allocated_hours, 11, "The allocated hours should equal the whole length of the slot inside the contract period of a fully flexible employee")

        # 2) Set a flexible contract for another employee
        flexible_calendar = self.flexible_calendar_30_6
        self.employee_janice.version_id.write({
            'date_version': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_end': datetime.strptime('2015-12-16', '%Y-%m-%d'),
            'name': 'Flex contract for Janice',
            'resource_calendar_id': flexible_calendar.id,
            'wage': 5000.0,
        })

        # Create a slot outside the contract period
        slot_outside = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 17, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 12, 0, 0),
            'resource_ids': self.resource_janice.ids,
        })
        self.assertEqual(slot_outside.allocated_hours, 0, "The allocated hours should be 0 for a slot outside the contract period of a flexible employee")

        # Create a slot inside the contract period
        slot_inside = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 16, 14, 0, 0),
            'resource_ids': self.resource_janice.ids,
        })
        self.assertEqual(slot_inside.allocated_hours, 6, "The allocated hours should be 6 for a slot inside the contract period of a flexible employee")

        # 3) Set a flexible contract with no end date for another employee
        flexible_calendar_no_end = self.flexible_calendar_30_6
        self.employee_janice.create_version({
            'date_version': datetime.strptime('2016-01-16', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2016-01-16', '%Y-%m-%d'),
            'contract_date_end': False,
            'name': 'Flex contract for Janice with no end date',
            'resource_calendar_id': flexible_calendar_no_end.id,
            'wage': 5000.0,
        })

        slot_inside = self.env['planning.slot'].create({
            'start_datetime': datetime(2016, 1, 16, 8, 0, 0),
            'end_datetime': datetime(2016, 1, 16, 14, 0, 0),
            'resource_ids': self.resource_janice.ids,
        })
        self.assertEqual(slot_inside.allocated_hours, 6, "The allocated hours should be 6 for a slot inside the contract period of a flexible employee with no end date")

    def test_allocated_hours_of_slot_overlapping_with_contract_period(self):
        """
            When a flexible or fully flexible employee plan a slot partially outside the period of
            the contract, the pre-computed allocated hours should be the hours within the contract period.
        """

        # 1) Set a fully flexible contract for an employee
        fully_flexible_calendar = self.fully_flexible_calendar
        self.employee_joseph.version_id.write({
            'date_version': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_end': datetime.strptime('2015-12-16', '%Y-%m-%d'),    # contract will end at 2015-12-16 23:59:59
            'name': 'Fully flex contract for Joseph',
            'resource_calendar_id': fully_flexible_calendar.id,
            'wage': 5000.0,
        })

        # Create a slot partially outside the contract period
        slot_outside = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 12, 0, 0),
            'resource_ids': self.resource_joseph.ids,
        })
        self.assertEqual(slot_outside.allocated_hours, 16.0, "The allocated hours should be 16h (8AM to 12PM) of the 16th of December for the fully flexible employee")

        # 2) Set a flexible contract for another employee
        flexible_calendar = self.flexible_calendar_30_6
        self.employee_janice.version_id.write({
            'date_version': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_end': datetime.strptime('2015-12-16', '%Y-%m-%d'),
            'name': 'Flex contract for Janice',
            'resource_calendar_id': flexible_calendar.id,
            'wage': 5000.0,
        })

        # Create a slot partially outside the contract period
        slot_outside = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 8, 0, 0),
            'resource_ids': self.resource_janice.ids,
        })
        self.assertEqual(slot_outside.allocated_hours, 6.0, "The allocated hours should be 6h (the max per day) for the flexible employee")

    def test_allocated_hours_on_open_shift(self):
        slot = self.env['planning.slot'].create({
            'start_datetime': datetime(2015, 12, 16, 8, 0, 0),
            'end_datetime': datetime(2015, 12, 17, 8, 0, 0),
        })
        self.assertEqual(slot.allocated_hours, 8, "The allocated hours should be computed without any issue")

    def test_plan_service_request_action_filters(self):
        role = self.env['planning.role'].create({
            'name': 'Test Role',
            'resource_ids': self.resource_joseph.ids,
        })

        slot = self.env['planning.slot'].create({
            'name': 'Test Service Request',
            'role_id': role.id,
            'start_datetime': False,
            'end_datetime': False,
        })
        action = slot.action_plan_shift()
        self.assertEqual(action['context']['search_default_role_id'], role.id, "The role should be set as the default filter.")
        self.assertEqual(action['context']['filter_resource_ids'], role.resource_ids.ids, "The role's resources should be used as the resource filter")

        slot.write({'role_id': False})
        action = slot.action_plan_shift()
        self.assertEqual(action['context']['search_default_role_id'], False)
        self.assertEqual(action['context']['filter_resource_ids'], [])
