# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, UTC
from zoneinfo import ZoneInfo
from odoo.tests.common import tagged, TransactionCase


@tagged('-at_install', 'post_install')
class TestHrAttendanceGantt(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Shared flexible calendars, reused across the flexible-schedule tests below instead of
        # each one creating its own.
        cls.flexible_calendar_40_8, cls.fully_flexible_calendar = cls.env['resource.calendar'].create([
            {
                'name': 'Flexible Calendar 40h/week',
                'calendar_type': 'undefined',
                'attendance_ids': [],
                'hours_per_week': 40,
                'hours_per_day': 8,
            },
            {
                'name': 'Fully Flexible Calendar',
                'calendar_type': 'undefined',
                'attendance_ids': [],
            },
        ])

    def test_gantt_progress_bar(self):
        calendar_8 = self.env['resource.calendar'].create({
            'name': 'Calendar 8h',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 9, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 12, 'hour_to': 17}),
            ]
        })

        calendar_10 = self.env['resource.calendar'].create({
            'name': 'Calendar 10h',
            'hours_per_day': 10.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 9, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 12, 'hour_to': 19}),
            ]
        })

        calendar_12 = self.env['resource.calendar'].create({
            'name': 'Calendar 12h',
            'hours_per_day': 12.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 9, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 12, 'hour_to': 21}),
            ]
        })

        contract_emp = self.env['hr.employee'].create({
            'name': "Johhny Contract",
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 10,
            'resource_calendar_id': calendar_8.id,
        })

        contract_emp.create_version({
            'date_version': date(2024, 2, 1),
            'resource_calendar_id': calendar_10.id,
            'wage': 10,
        })
        contract_emp.create_version({
            'date_version': date(2024, 3, 1),
            'resource_calendar_id': calendar_12.id,
            'wage': 10,
        })

        contract_emp1 = self.env['hr.employee'].create({
            'name': "John Contract",
            'date_version': date(2024, 2, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 10,
            'resource_calendar_id': calendar_8.id,
        })

        contract_emp1.create_version({
            'date_version': date(2024, 3, 1),
            'resource_calendar_id': calendar_10.id,
            'wage': 10,
        })
        contract_emp1.create_version({
            'date_version': date(2024, 4, 1),
            'resource_calendar_id': calendar_12.id,
            'wage': 10,
        })

        # First Interval in January
        # should have 8 hours

        interval_1 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                  [contract_emp.id],
                                                                  datetime(2024, 1, 8),
                                                                  datetime(2024, 1, 14))

        self.assertEqual(interval_1[contract_emp.id]['max_value'], 8)

        # Second Interval in January
        # should have 10 hours

        interval_1 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                   [contract_emp.id],
                                                                   datetime(2024, 2, 8),
                                                                   datetime(2024, 2, 14))

        self.assertEqual(interval_1[contract_emp.id]['max_value'], 10)

        # Third Interval in March
        # should have 12 hours

        interval_2 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                  [contract_emp.id],
                                                                  datetime(2024, 3, 4),
                                                                  datetime(2024, 3, 10))

        self.assertEqual(interval_2[contract_emp.id]['max_value'], 12)

        # First Interval in January
        # should have 8 hours

        interval_1 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                  [contract_emp1.id],
                                                                  datetime(2024, 1, 8),
                                                                  datetime(2024, 1, 14))

        self.assertEqual(interval_1[contract_emp1.id]['max_value'], 8)

        # Second Interval in January ending and February starting
        # should have 8 hours

        interval_2 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                  [contract_emp1.id],
                                                                  datetime(2024, 1, 29),
                                                                  datetime(2024, 2, 5))

        self.assertEqual(interval_1[contract_emp1.id]['max_value'], 8)

        # Third Interval in March
        # should have 10 hours

        interval_3 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                   [contract_emp1.id],
                                                                   datetime(2024, 3, 8),
                                                                   datetime(2024, 3, 14))

        self.assertEqual(interval_3[contract_emp1.id]['max_value'], 10)

        # Fourth Interval in April
        # should have 12 hours

        interval_4 = self.env['hr.attendance']._gantt_progress_bar('employee_id',
                                                                  [contract_emp1.id],
                                                                  datetime(2024, 4, 4),
                                                                  datetime(2024, 4, 10))

        self.assertEqual(interval_4[contract_emp1.id]['max_value'], 12)

    def test_gantt_progress_with_flexible_employees(self):
        calendar = self.env['resource.calendar'].create([
            {
                'name': 'Calendar 8h',
                'company_id': False,
                'full_time_required_hours': 8.0,
                'hours_per_day': 8.0,
                'attendance_ids': [
                    (0, 0, {'dayofweek': '0', 'hour_from': 9, 'hour_to': 12}),
                    (0, 0, {'dayofweek': '0', 'hour_from': 12, 'hour_to': 17}),
                ],
            },
        ])

        flexible_calendar_8h = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar 8h',
            'company_id': False,
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 8,
            'hours_per_day': 8,
        })
        emp1, emp2 = self.env['hr.employee'].create([
            {'name': 'freelance1', 'resource_calendar_id': flexible_calendar_8h.id, 'tz': 'UTC'},
            {'name': 'freelance2', 'resource_calendar_id': calendar.id, 'tz': 'UTC'},
        ])
        self.assertTrue(emp1._is_flexible())
        self.assertFalse(emp2._is_flexible())
        emp2.write({
            'resource_calendar_id': flexible_calendar_8h.id,
        })  # emp2 should now have a flexible hours as well

        interval = self.env['hr.attendance']._gantt_progress_bar(
            'employee_id',
            [emp1.id, emp2.id],
            datetime(2024, 1, 8),
            datetime(2024, 1, 15),
        )

        self.assertEqual(interval[emp1.id]['max_value'], 8)
        self.assertEqual(interval[emp2.id]['max_value'], 8)  # flexible employee with hours_per_week = 8

        # If the user is not in UTC time, the start and stop datetimes will not at midnight.
        # This could cause issues with the calculation of attendance intervals and, in turn, max_value.
        # This block simulates this case. We'll simulate in Europe/Zurich time

        self.env.user.write({'tz': 'Europe/Zurich'})  # UTC+2 (summer) or UTC+1 (winter)
        interval_non_utc = self.env['hr.attendance']._gantt_progress_bar(
            'employee_id',
            [emp1.id, emp2.id],
            datetime(2024, 1, 7, 22, 0),
            datetime(2024, 1, 14, 22, 0),
        )

        # The max value should be the same, regardless of the browser timezone
        self.assertEqual(interval_non_utc[emp1.id]['max_value'], 8)
        self.assertEqual(interval_non_utc[emp2.id]['max_value'], 8)

    def test_gantt_unavailability(self):
        self.calendar = self.env['resource.calendar'].create({
            'name': 'Calendar 8h',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
            ],
        })
        fully_flex_calendar = self.fully_flexible_calendar
        self.fully_flex_emp = self.env['hr.employee'].create({
            'name': 'Fully Flex Emp',
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 10,
            'resource_calendar_id': fully_flex_calendar.id,
            'tz': 'UTC',
        })
        self.regular_emp = self.env['hr.employee'].create({
            'name': 'Regular Emp',
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'wage': 10,
            'resource_calendar_id': self.calendar.id,
            'tz': 'UTC',
        })

        unavailabilities = self.env['hr.attendance']._gantt_unavailability(
            'employee_id',
            [self.fully_flex_emp.id, self.regular_emp.id],
            datetime(2024, 1, 2, tzinfo=UTC),
            datetime(2024, 1, 3, tzinfo=UTC),
            'month',
        )
        expected_unavailabilities = {
            self.fully_flex_emp.id: [],
            self.regular_emp.id: [
                {'start': datetime(2024, 1, 2, 0, 0, tzinfo=UTC), 'stop': datetime(2024, 1, 2, 8, 0, tzinfo=UTC)},
                {'start': datetime(2024, 1, 2, 12, 0, tzinfo=UTC), 'stop': datetime(2024, 1, 2, 13, 0, tzinfo=UTC)},
                {'start': datetime(2024, 1, 2, 17, 0, tzinfo=UTC), 'stop': datetime(2024, 1, 3, 0, 0, tzinfo=UTC)},
            ],
        }
        self.assertEqual(unavailabilities, expected_unavailabilities)

    def test_attendance_gantt_unavailabilities_flexible_employee(self):
        flexible_calendar_40h = self.flexible_calendar_40_8
        employee = self.env['hr.employee'].create({
            'name': 'Flex Employee',
            'date_version': date(2019, 1, 1),
            'contract_date_start': date(2019, 1, 1),
            'contract_date_end': date(2019, 7, 29),
            'wage': 10,
            'tz': 'UTC',
            'resource_calendar_id': flexible_calendar_40h.id,
        })

        unavailabilities = self.env['hr.attendance']._gantt_unavailability(
            'employee_id',
            [employee.id],
            datetime(2019, 1, 1),
            datetime(2019, 1, 7),
            'week',
        )
        self.assertEqual(unavailabilities[employee.id], [])

        public_holiday = self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime(2019, 1, 5, 0, 0, 0),
            'date_to': datetime(2019, 1, 5, 23, 59, 59),
        })

        unavailabilities = self.env['hr.attendance']._gantt_unavailability(
            'employee_id',
            [employee.id],
            datetime(2019, 1, 1),
            datetime(2019, 1, 7),
            'week',
        )
        self.assertEqual(unavailabilities[employee.id][0]['start'], public_holiday.date_from.astimezone(UTC))
        self.assertEqual(unavailabilities[employee.id][0]['stop'], public_holiday.date_to.astimezone(UTC))

    def test_gantt_unavailability_duration_based(self):
        """
        For an employee on a duration-based schedule, he should be available for the whole day
        """

        duration_calendar = self.env['resource.calendar'].create({
            'name': 'Duration-based 8h Calendar',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 8}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 8}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 8}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 8}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 8}),
            ],
        })

        employee = self.env['hr.employee'].create({
            'name': 'Duration Based Employee',
            'date_version': date(2026, 3, 1),
            'contract_date_start': date(2026, 3, 1),
            'contract_date_end': date(2026, 7, 29),
            'wage': 1000,
            'resource_calendar_id': duration_calendar.id,
            'tz': 'UTC',
        })
        # When no leaves are taken , the whole day should be available
        unavailabilities = self.env['hr.attendance']._gantt_unavailability(
            'employee_id',
            [employee.id],
            datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
            datetime(2026, 3, 20, 0, 0, tzinfo=UTC),
            'day',
        )
        self.assertEqual(unavailabilities[employee.id], [])

    def test_attendances_intervals_different_timezones(self):
        """
        Checks that if a flexible schedule has an attendance of 40 hours per week, the expected hours for a week
        stay at 40 hours, even if we change the timezone.
        """
        flexible_calendar = self.flexible_calendar_40_8
        employee = self.env['hr.employee'].create({
            'name': 'Test',
            'contract_date_start': '2026-02-01',
            'resource_calendar_id': flexible_calendar.id,
            'tz': 'America/Recife',
        })
        employee.resource_id.write({
            'tz': 'Europe/Brussels'
        })
        interval_west = self.env['hr.attendance']._gantt_progress_bar(
            'employee_id',
            [employee.id],
            datetime(2024, 1, 8),
            datetime(2024, 1, 15),
        )
        self.assertAlmostEqual(interval_west[employee.id]['max_value'], 40)
        employee.write({'tz': 'UTC'})
        interval_central = self.env['hr.attendance']._gantt_progress_bar(
            'employee_id',
            [employee.id],
            datetime(2024, 1, 8),
            datetime(2024, 1, 15),
        )
        self.assertAlmostEqual(interval_central[employee.id]['max_value'], 40)
        employee.write({'tz': 'Asia/Pyongyang'})
        interval_east = self.env['hr.attendance']._gantt_progress_bar(
            'employee_id',
            [employee.id],
            datetime(2024, 1, 8),
            datetime(2024, 1, 15),
        )
        self.assertAlmostEqual(interval_east[employee.id]['max_value'], 40)

    def test_time_off_hours_with_flex_schedule_timezone(self):
        """
        Checks that the start and end hours of a time off shown in the attendance calendar taken under a flexible
        schedule with a timezone other than UTC are correct. When the schedule is flexible, the hours from midnight to
        midnight the next day should be grayed out.
        """
        self.env.user.tz = 'Europe/Brussels'
        tz = ZoneInfo('Europe/Brussels')
        flexible_calendar = self.fully_flexible_calendar
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'tz': 'Europe/Brussels',
            'date_version': date(2019, 1, 1),
            'contract_date_start': date(2019, 1, 1),
            'resource_calendar_id': flexible_calendar.id,
        })
        self.env['resource.calendar.leaves'].create({
            'name': 'Time off',
            'resource_id': employee.resource_id.id,
            'date_from': datetime(2019, 1, 5, 8, 0, 0),
            'date_to': datetime(2019, 1, 5, 16, 0, 0),
        })
        unavailabilities = self.env['hr.attendance']._gantt_unavailability(
            'employee_id',
            [employee.id],
            datetime(2019, 1, 5, 0, 0, tzinfo=tz),
            datetime(2019, 1, 5, 23, 59, 59, tzinfo=tz),
            'day',
        )
        self.assertEqual(unavailabilities[employee.id][0]['start'], datetime(2019, 1, 4, 23, 0).astimezone(UTC))
        self.assertEqual(unavailabilities[employee.id][0]['stop'], datetime(2019, 1, 5, 22, 59, 59).astimezone(UTC))
