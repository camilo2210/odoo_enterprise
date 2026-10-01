# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date, datetime, UTC
from unittest.mock import patch
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tests import Form

from odoo.addons.hr_holidays.tests.common import TestHolidayContract
from odoo.addons.mail.tests.common import mail_new_test_user


class TestHrLeaveGantt(TestHolidayContract):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.jules_emp.tz = 'UTC'
        cls.company = cls.env["res.company"].create(
            {
                "name": "Empresa de Tumbonas",
            },
        )
        cls.employees_with_leaves = cls.env['hr.employee'].create(
            [
                {'name': f'Sr. Left {i}', 'company_id': cls.company.id}
                for i in range(19)
            ],
        )
        for employee in cls.employees_with_leaves:
            cls.create_leave(
                date_from=datetime(2025, 11, 20, 7),
                date_to=datetime(2025, 11, 20, 18),
                name="Tumbona Time",
                employee_id=employee.id,
            )

        cls.employees_without_leaves = cls.env['hr.employee'].create(
            [
                {'name': f'Sir Right {i}', 'company_id': cls.company.id}
                for i in range(13)
            ],
        )
        cls.all_employees = (
            cls.employees_with_leaves + cls.employees_without_leaves
        )

        # to filter out employees that may be created in the parent class
        cls.all_employees_domain = Domain(
            'employee_id',
            'in',
            cls.all_employees.mapped('id'),
        )

    def _assert_returned_ids_equals_employee_list(
        self,
        returned_ids: set[int],
        employees,
    ) -> None:
        self.assertEqual(
            returned_ids,
            set(employees.mapped('id')),
            "get_gantt_data did not return the correct list of employees",
        )

    def _get_gantt_data_ids(
        self,
        user_domain: Domain,
    ) -> set[int]:
        """
        Wrapper for get_gantt_data() to remove repeated boilerplate
        """
        groupby = ['employee_id']
        read_specification = {}
        gantt_result = self.env['hr.leave'].with_context(user_domain=user_domain).get_gantt_data(
            user_domain,
            groupby,
            read_specification,
            limit=None,
            offset=0,
            unavailability_fields=['employee_id'],
            progress_bar_fields=['employee_id'],
            start_date='2025-11-01 00:00:00',
            stop_date='2025-11-30 00:00:00',
            scale='month',
        )
        return {group['employee_id'][0] for group in gantt_result['groups']}

    def test_gantt_split_leave(self):
        """ The gantt "scissors" splits a multi-day time off in two and can be
        undone, restoring the original time off. """
        employee = self.env['hr.employee'].create({
            'name': 'Split Tester',
            'company_id': self.company.id,
        })
        leave = self.create_leave(
            date_from=datetime(2025, 12, 1),  # Monday
            date_to=datetime(2025, 12, 5),  # Friday
            name="To be split",
            employee_id=employee.id,
        )
        self.assertEqual(leave.request_date_from, date(2025, 12, 1))
        self.assertEqual(leave.request_date_to, date(2025, 12, 5))

        undo_data = leave.gantt_split_leave('2025-12-03')  # Wednesday

        # The original time off is truncated to end the day before the split.
        self.assertEqual(leave.request_date_from, date(2025, 12, 1))
        self.assertEqual(leave.request_date_to, date(2025, 12, 2))

        # A single new time off is created for the second part.
        self.assertEqual(len(undo_data['new_leave_ids']), 1)
        new_leave = self.env['hr.leave'].browse(undo_data['new_leave_ids'])
        self.assertEqual(new_leave.employee_id, employee)
        self.assertEqual(new_leave.request_date_from, date(2025, 12, 3))
        self.assertEqual(new_leave.request_date_to, date(2025, 12, 5))

        # Undoing the split removes the new time off and restores the original.
        result = leave.gantt_undo_split_leave(
            undo_data['new_leave_ids'],
            undo_data['request_date_to'],
            undo_data['request_date_to_period'],
        )
        self.assertTrue(result)
        self.assertFalse(new_leave.exists())
        self.assertEqual(leave.request_date_from, date(2025, 12, 1))
        self.assertEqual(leave.request_date_to, date(2025, 12, 5))

    def _create_validated_leave(self, employee, date_from=datetime(2027, 1, 4),
                                date_to=datetime(2027, 1, 6)):
        """ Create a time off and put it in the validated state. The approval
        machinery itself is not what these tests cover, so the state is set
        directly (bypassing only the unrelated date-warning check). """
        leave = self.create_leave(
            date_from=date_from,
            date_to=date_to,
            name="Approved time off",
            employee_id=employee.id,
        )
        leave.sudo().with_context(leave_skip_date_check=True).write({'state': 'validate'})
        self.assertEqual(leave.state, 'validate')
        return leave

    def test_validated_leave_dates_are_read_only(self):
        """ _check_date_state forbids editing the dates of a validated time off;
        that is why the popover opens read-only until "Edit". """
        employee = self.env['hr.employee'].create({
            'name': 'Locked Dates',
            'company_id': self.company.id,
        })
        leave = self._create_validated_leave(employee)

        with self.assertRaises(ValidationError):
            leave.write({'request_date_to': date(2027, 1, 8)})
            leave.flush_recordset()

    def test_edit_dates_after_back_to_approval(self):
        """ Once sent back to approval the dates become editable again: this is
        the popover "Edit -> modify -> Save" flow. """
        employee = self.env['hr.employee'].create({
            'name': 'Edit After Back',
            'company_id': self.company.id,
        })
        leave = self._create_validated_leave(employee)

        leave.sudo().action_back_to_approval()
        leave.write({'request_date_to': date(2027, 1, 8)})
        leave.flush_recordset()

        self.assertEqual(leave.state, 'confirm')
        self.assertEqual(leave.request_date_to, date(2027, 1, 8))

    def test_gantt_undo_split_validated_leave(self):
        """ Undoing a split must also work on a validated time off: the original
        end date is restored through the leave_skip_state_check context instead
        of being rejected by _check_date_state. """
        employee = self.env['hr.employee'].create({
            'name': 'Validated Split',
            'company_id': self.company.id,
        })
        leave = self._create_validated_leave(
            employee,
            date_from=datetime(2027, 1, 4),  # Monday
            date_to=datetime(2027, 1, 8),  # Friday
        )

        undo_data = leave.gantt_split_leave('2027-01-06')  # Wednesday
        self.assertEqual(leave.request_date_to, date(2027, 1, 5))
        new_leave = self.env['hr.leave'].browse(undo_data['new_leave_ids'])
        self.assertTrue(new_leave.exists())

        result = leave.gantt_undo_split_leave(
            undo_data['new_leave_ids'],
            undo_data['request_date_to'],
            undo_data['request_date_to_period'],
        )

        self.assertTrue(result)
        self.assertFalse(new_leave.exists())
        self.assertEqual(leave.request_date_to, date(2027, 1, 8))
        self.assertEqual(leave.state, 'validate')

    def test_get_gantt_data_employee_fields(self):
        """
        Employees without leaves should not be automatically filtered if domain
        is only about employee fields
        """
        returned_ids = self._get_gantt_data_ids(
            self.all_employees_domain,
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.all_employees,
        )

    def test_get_gantt_data_attendance_domain(self):
        """
        Employees without leaves should not be in the return value since the
        field is not related to hr.employee
        """
        returned_ids = self._get_gantt_data_ids(
            Domain('date_from', '<', '2025-12-01')
            & self.all_employees_domain,
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.employees_with_leaves,
        )

    def test_gantt_view_without_schedule(self):
        """
        Test that the Time Off Gantt view works correctly even
        when an employee contract has a fully flexible working schedule.
        """
        # Assign a fully flexible working schedule (resource calendar) to the employee's contract
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
        })
        self.contract_cdi.write({
            'date_start': datetime.strptime('2025-01-01', '%Y-%m-%d').date(),
            'date_end': datetime.strptime('2025-12-31', '%Y-%m-%d').date(),
            'resource_calendar_id': flexible_calendar.id,
        })

        # Create a time off for the employee
        self.create_leave(
            date_from=datetime(2025, 11, 11, 7),
            date_to=datetime(2025, 11, 11, 18),
            name="Doctor Appointment",
            employee_id=self.jules_emp.id,
        )

        # Get the Gantt overview data for employees's time off data
        gantt_domain = Domain('employee_id.active', '=', True)
        group_employee_ids = self._get_gantt_data_ids(gantt_domain)

        self.assertIn(
            self.jules_emp.id,
            group_employee_ids,
            "The employee should be in the gantt data groups.",
        )

    def test_gantt_view_access(self):
        """
        Test timeoff gantt report when filtering by employee domain only
        The employe domain filter uses a shortcut searching by public employee domain
        """
        regular_user = mail_new_test_user(
            self.env,
            email='regular_user@example.com',
            login='regular_user',
            name='Regular User',
            groups='base.group_user,hr_holidays.group_hr_holidays_employee',
        )

        start_date = datetime.strptime('2025-11-11 07:00:00', '%Y-%m-%d %H:%M:%S')
        stop_date = datetime.strptime('2025-11-11 18:00:00', '%Y-%m-%d %H:%M:%S')
        self.create_leave(start_date, stop_date, name="Doctor Appointment", employee_id=self.jules_emp.id)

        gantt_domain = [('employee_id.active', '=', True), ("department_id", "=", self.jules_emp.department_id.id)]
        try:
            self.env["hr.leave.report.calendar"].with_user(regular_user).with_company(self.jules_emp.company_id).get_gantt_data(
                gantt_domain,
                ["employee_id"],
                {},
                start_date=start_date,
                stop_date=stop_date,
            )
        except ValueError as e:
            self.assertNotIn("current_version_id", str(e), "The effective domain is not translated properly to hr.employee.public")
            raise

    def test_gantt_unavailability_versions_different_timezones(self):
        """ A schedule is unavailable at the same wall clock whichever timezone its
        version is kept in. """
        # employee with two versions on the same calendar but different timezones
        self.env.user.tz = 'Europe/Brussels'
        self.contract_cdd.resource_calendar_id = self.calendar_40h
        self.contract_cdi.resource_calendar_id = self.calendar_40h
        self.contract_cdd.tz = 'Europe/Brussels'
        self.contract_cdi.tz = 'Asia/Tokyo'

        self.create_leave(datetime(2015, 11, 10), datetime(2015, 11, 10), name="Leave", employee_id=self.jules_emp.id)

        gantt_data = self.env['hr.leave'].get_gantt_data(
            [('employee_id', '=', self.jules_emp.id)],
            ['employee_id'],
            {},
            unavailability_fields=['employee_id'],
            start_date='2015-11-09 00:00:00',  # before the CDD ends
            stop_date='2015-11-21 00:00:00',  # after the CDI starts
            scale='week',
        )
        unavailabilities = gantt_data['unavailabilities']['employee_id'][self.jules_emp.id]
        self.assertEqual(
            self.env['hr.leave.report.calendar']._gantt_unavailability(
                'employee_id', [self.jules_emp.id],
                datetime(2015, 11, 9), datetime(2015, 11, 21), 'week'),
            {self.jules_emp.id: unavailabilities},
            "the overview greys the cells this gantt greys",
        )

        def is_unavailable(dt):
            return any(interval['start'] <= dt < interval['stop'] for interval in unavailabilities)

        def read_on_the_gantt(day, hour):
            return datetime(2015, 11, day, hour, 30, tzinfo=ZoneInfo('Europe/Brussels'))

        # Saturday is unavailable whatever the timezone
        self.assertTrue(is_unavailable(datetime(2015, 11, 14, 12, 0, tzinfo=UTC)))
        # the CDD version is kept in Brussels, the CDI one in Tokyo
        for day, version in ((10, 'CDD'), (18, 'CDI')):
            self.assertFalse(
                is_unavailable(read_on_the_gantt(day, 9)),
                f"09:30 on the gantt is a working time of the {version} version",
            )
            self.assertTrue(
                is_unavailable(read_on_the_gantt(day, 6)),
                f"06:30 on the gantt is before the working time of the {version} version",
            )

    def test_splitting_a_request_in_hours_and_undoing_it(self):
        """ Undoing a split puts back the hour the request ended on. """
        custom_hours = self.env['hr.work.entry.type'].create({
            'name': 'Custom Hours', 'code': 'test_custom_hours', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'request_unit': 'hour',
            'unit_of_measure': 'hour', 'count_as': 'absence',
        })
        leave = self.env['hr.leave'].create({
            'name': 'Two days and a morning', 'employee_id': self.jules_emp.id,
            'work_entry_type_id': custom_hours.id,
            'request_date_from': date(2015, 11, 18), 'request_date_to': date(2015, 11, 20),
            'request_hour_from': 8, 'request_hour_to': 12, 'request_duration': 'specific',
        })
        whole = leave.number_of_hours

        undo_data = leave.gantt_split_leave('2015-11-20')
        rest = self.env['hr.leave'].browse(undo_data['new_leave_ids'])
        self.assertEqual(leave.request_date_to, date(2015, 11, 19))
        self.assertEqual(leave.request_hour_to, 16, "the first part ends with its own last day")
        self.assertEqual(leave.number_of_hours + rest.number_of_hours, whole,
                         "the two parts hold what the request held")

        leave.gantt_undo_split_leave(undo_data['new_leave_ids'], undo_data['request_date_to'],
                                    undo_data['request_date_to_period'], undo_data['request_hour_to'])
        self.assertEqual((leave.request_date_to, leave.request_hour_to), (date(2015, 11, 20), 12))
        self.assertEqual(leave.number_of_hours, whole)

    def test_gantt_unavailability_is_told_in_utc(self):
        """ The greyed cells travel without their offset and are read back as UTC. """
        self.env.user.tz = 'Europe/Brussels'
        self.contract_cdi.tz = 'Europe/Brussels'
        start = datetime(2015, 11, 20, 23, 0)  # Saturday 2015-11-21 00:00 in Brussels
        stop = datetime(2015, 11, 30, 23, 0)
        unavailabilities = self.env['hr.leave']._gantt_unavailability(
            'employee_id', [self.jules_emp.id], start, stop, 'month')

        self.assertEqual(
            fields.Datetime.to_string(unavailabilities[self.jules_emp.id][0]['start']),
            fields.Datetime.to_string(start),
            "the first cell is unavailable from the very start of the window",
        )

    def test_gantt_progress_bar_follows_the_timezone_of_the_reader(self):
        """ The bar counts the days the row shows: the window it sums over is the one the
        reader sees, told by the clock of the employee. """
        mondays_only = self.env['resource.calendar'].create({
            'name': 'Mondays only',
            'attendance_ids': [(0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 16,
                                       'day_period': 'full_day'})],
        })
        self.contract_cdi.write({
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': date(2025, 12, 31),
            'resource_calendar_id': mondays_only.id,
        })
        # the Monday cell of a reader in Brussels, whichever clock the employee keeps
        self.env.user.tz = 'Europe/Brussels'
        start = datetime(2025, 3, 2, 23, 0)  # Monday 2025-03-03 00:00 in Brussels
        stop = datetime(2025, 3, 3, 23, 0)   # the Tuesday
        for tz in ('Europe/Brussels', 'Asia/Tokyo', 'America/New_York', 'Pacific/Pago_Pago'):
            self.contract_cdi.tz = self.jules_emp.tz = tz
            progress_bars = self.env['hr.leave']._gantt_progress_bar(
                'employee_id', [self.jules_emp.id], start, stop,
            )
            self.assertEqual(
                progress_bars[self.jules_emp.id]['value'], 8.0,
                f"the whole Monday of an employee kept in {tz} belongs to that cell",
            )

    def test_gantt_progress_bar_working_time_leave(self):
        self.contract_cdi.write({
            'date_start': datetime.strptime('2025-01-01', '%Y-%m-%d').date(),
            'date_end': datetime.strptime('2025-12-31', '%Y-%m-%d').date(),
            'resource_calendar_id': self.calendar_40h.id,
        })

        start = datetime.strptime('2025-03-03 00:00:00', '%Y-%m-%d %H:%M:%S')  # Monday
        stop = datetime.strptime('2025-03-07 23:59:59', '%Y-%m-%d %H:%M:%S')   # Friday

        progress_no_leave = self.env['hr.leave']._gantt_progress_bar(
            'employee_id', [self.jules_emp.id], start, stop,
        )
        hours_no_leave = progress_no_leave[self.jules_emp.id]['value']
        self.assertEqual(hours_no_leave, 40.0)

        working_time_type = self.env['hr.work.entry.type'].create({
            'name': 'Training',
            'code': 'TRAIN',
            'count_as': 'working_time',
            'requires_allocation': False,
            'request_unit': 'day',
            'unit_of_measure': 'day',
        })

        leave = self.env['hr.leave'].create({
            'name': 'Training Day',
            'employee_id': self.jules_emp.id,
            'work_entry_type_id': working_time_type.id,
            'request_date_from': datetime.strptime('2025-03-05', '%Y-%m-%d'),
            'request_date_to': datetime.strptime('2025-03-05', '%Y-%m-%d'),
        })
        leave.action_approve()

        progress_with_leave = self.env['hr.leave']._gantt_progress_bar(
            'employee_id', [self.jules_emp.id], start, stop,
        )
        hours_with_working_time = progress_with_leave[self.jules_emp.id]['value']
        self.assertEqual(hours_with_working_time, 40.0)

    def test_gantt_view_flex_schedule_time_off_types(self):
        """Checks that the correct areas are grayed out when an employee with a flexible schedule takes days off
        when the type of these days off are either half-days or hours."""
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 56,
            'hours_per_day': 8,
        })
        self.jules_emp.write({'resource_calendar_id': flexible_calendar.id})
        work_entry_type_half_day, work_entry_type_hours = self.env['hr.work.entry.type'].create([{
            'name': 'Half day',
            'count_as': 'absence',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'code': 'HALF',
            'unit_of_measure': 'day',
        }, {
            'name': 'Hours',
            'count_as': 'absence',
            'requires_allocation': False,
            'request_unit': 'hour',
            'code': 'HOURS',
            'unit_of_measure': 'hour',
        }])
        half_day_leave, hours_leave = self.env['hr.leave'].create([{
            'name': 'Half Day Leave',
            'work_entry_type_id': work_entry_type_half_day.id,
            'employee_id': self.jules_emp.id,
            'request_date_from': datetime(2026, 3, 24),
            'request_date_to': datetime(2026, 3, 24),
            'request_date_from_period': 'am',
            'request_date_to_period': 'am',
            'work_entry_type_request_unit': 'half_day',
        }, {
            'name': 'Hour Leave',
            'work_entry_type_id': work_entry_type_hours.id,
            'employee_id': self.jules_emp.id,
            'request_date_from': datetime(2026, 3, 25),
            'request_date_to': datetime(2026, 3, 25),
            'request_hour_from': 12.0,
            'request_hour_to': 16.0,
            'work_entry_type_request_unit': 'hour',
        }])
        self.env['resource.calendar.leaves'].create([{
            'resource_id': self.jules_emp.resource_id.id,
            'date_from': datetime(2026, 3, 24, 8, 0, 0),
            'date_to': datetime(2026, 3, 24, 12, 0, 0),
            'holiday_id': half_day_leave.id,
            'count_as': 'absence',
        }, {
            'resource_id': self.jules_emp.resource_id.id,
            'date_from': datetime(2026, 3, 25, 12, 0, 0),
            'date_to': datetime(2026, 3, 25, 16, 0, 0),
            'holiday_id': hours_leave.id,
            'count_as': 'absence',
        }])
        half_day_leave.action_approve()
        hours_leave.action_approve()
        start_date_half = '2026-03-24 00:00:00'
        stop_date_half = '2026-03-24 23:59:59'

        gantt_domain = [('employee_id', '=', self.jules_emp.id)]

        read_specification = {'can_approve': {}, 'can_refuse': {}, 'can_validate': {}, 'color': {}, 'date_from': {}, 'date_to': {}, 'display_name': {}, 'employee_id': {'fields': {'display_name': {}}}, 'number_of_days': {}, 'state': {}, 'work_entry_type_id': {'fields': {'display_name': {}}}}
        gantt_data_half = self.env['hr.leave'].with_context(allowed_company_ids=self.jules_emp.company_id.ids).get_gantt_data(
            gantt_domain, ['employee_id'], read_specification, unavailability_fields=['employee_id'],
            progress_bar_fields=['employee_id'], start_date=start_date_half, stop_date=stop_date_half, scale='day')
        self.assertEqual(gantt_data_half['progress_bars']['employee_id'][self.jules_emp.id]['value'], 4)

        start_date_hour = '2026-03-25 00:00:00'
        stop_date_hour = '2026-03-25 23:59:59'
        gantt_data_hour = self.env['hr.leave'].with_context(allowed_company_ids=self.jules_emp.company_id.ids).get_gantt_data(
            gantt_domain, ['employee_id'], read_specification, unavailability_fields=['employee_id'],
            progress_bar_fields=['employee_id'], start_date=start_date_hour, stop_date=stop_date_hour, scale='day')
        self.assertEqual(gantt_data_hour['progress_bars']['employee_id'][self.jules_emp.id]['value'], 4)

    def test_gantt_data_only_shows_employees_from_selected_company(self):
        """
        Only employees from the selected companies should be shown in the gantt
        view (not the employees managed by the current user outside of the
        selected companies as well)

        This is so the gantt view doesn't try to access the employee's resource
        (in the _gantt_unavailability() function), which can't be accessed if
        not in a selected company

        We also verify that the returned unavailabilities are correctly put, to
        make sure that _gantt_unavailability() is still called (and not just
        ignored)
        """
        company_a = self.env['res.company'].create({'name': 'Horse Grindr'})
        company_b = self.env['res.company'].create({'name': 'Destroyer of Vegetables'})

        # create user/manager/employee for company A
        manager_user = mail_new_test_user(
            self.env,
            login='manager_gantt_test',
            name='Tung Tung Tung Sahur',
            groups='base.group_user,hr_holidays.group_hr_holidays_user',
            company_id=company_a.id,
            company_ids=[company_a.id],
        )
        manager_employee = self.env['hr.employee'].create({
            'name': 'Cappuccino Assassino',
            'user_id': manager_user.id,
            'company_id': company_a.id,
        })
        employee_in_company = self.env['hr.employee'].create({
            'name': 'Ballerina Cappuccina',
            'company_id': company_a.id,
            'resource_calendar_id': self.calendar_40h.id,
        })

        # employee managed by `manager_employee`, but in company B
        employee_outside_company = self.env['hr.employee'].create({
            'name': 'Tralalero Tralala',
            'company_id': company_b.id,
            'parent_id': manager_employee.id,
            'resource_calendar_id': self.calendar_40h.id,
        })

        # call gantt data function and extract the displayed employees
        gantt_domain = Domain('employee_id', 'in', (employee_in_company.id, employee_outside_company.id))
        gantt_result = (
            self.env['hr.leave.report.calendar']
            .with_user(manager_user)
            .with_context(
                allowed_company_ids=[company_a.id],
                user_domain=gantt_domain,
            )
            .get_gantt_data(
                gantt_domain,
                ['employee_id'],
                {},
                limit=None,
                offset=0,
                unavailability_fields=['employee_id'],
                progress_bar_fields=None,
                start_date='2025-06-01 00:00:00',
                stop_date='2025-06-30 23:59:59',
                scale='month',
            )
        )
        returned_employee_ids = {
            group['employee_id'][0]
            for group in gantt_result['groups']
            if group.get('employee_id')
        }

        self.assertIn(
            employee_in_company.id,
            returned_employee_ids,
            "Employee from the selected company should appear in the gantt.",
        )
        self.assertNotIn(
            employee_outside_company.id,
            returned_employee_ids,
            "Employee from outside the selected company must NOT appear in the "
            "gantt, even if they are managed by the current user.",
        )

        # also verify unavailabilities are set for the visible employee
        unavailabilities = gantt_result.get('unavailabilities', {}).get('employee_id', {})
        self.assertIn(
            employee_in_company.id,
            unavailabilities,
            "Unavailabilities should be returned for the visible company employee.",
        )
        self.assertTrue(
            len(unavailabilities[employee_in_company.id]) > 0,
            "There should be unavailability intervals for an employee with a "
            "standard 40h schedule over a full month.",
        )

    def test_gantt_view_employee_available_leave_types(self):
        """
        Checks that for each employee, correct available leave types are returned in the Gantt view.
        """
        belgian_company = self.env['res.company'].create({
            'name': 'Belgian Company',
            'country_id': self.env.ref('base.be').id,
        })

        leave_type_no_allocation_no_country, leave_type_no_allocation_belgium, leave_type_with_allocation = self.env['hr.work.entry.type'].create([
            {
                'name': 'No Allocation No Country',
                'country_id': False,
                'requires_allocation': False,
                'code': 'NO_ALLOC',
                'unit_of_measure': 'day',
            }, {
                'name': 'No Allocation Belgium',
                'country_id': self.env.ref('base.be').id,
                'requires_allocation': False,
                'code': 'NO_ALLOC',
                'unit_of_measure': 'day',
            }, {
                'name': 'With Allocation',
                'country_id': self.env.ref('base.be').id,
                'requires_allocation': True,
                'code': 'WITH_ALLOC',
                'unit_of_measure': 'day',
            },
        ])

        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': belgian_company.id,
            'country_id': self.env.ref('base.be').id
        })

        self.env['hr.leave.allocation'].create({
            'name': 'Test Allocation',
            'employee_id': employee.id,
            'state': 'confirm',
            'work_entry_type_id': leave_type_with_allocation.id,
            'number_of_days': 10,
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        }).action_approve()

        leave = self.env['hr.leave'].create({
            'name': '2 Days Off',
            'employee_id': employee.id,
            'work_entry_type_id': leave_type_with_allocation.id,
            'request_date_from': '2026-07-01',
            'request_date_to': '2026-07-02',
        })
        leave.action_approve()

        # Check available leave types when only one employee is selected in the Gantt view
        # Should return all leave types that do not require allocation and the leave type with valid allocations for the employee
        # If there are duplicate leave types (same code) for the employee's country and for no country,
        # the one with the employee's country should be returned
        available_types = employee.with_company(belgian_company).get_employee_available_leave_types()
        available_ids = [t['id'] for t in available_types]

        allocated_match = next((t for t in available_types if t['id'] == leave_type_with_allocation.id and t['requires_allocation']), None)
        self.assertIsNotNone(allocated_match, "Leave type with valid allocations should be available.")
        self.assertEqual(allocated_match['remaining_leaves'], 8.0)
        self.assertEqual(allocated_match['allocated_leaves'], 10.0)
        self.assertEqual(allocated_match['leaves_taken'], 2.0)
        self.assertEqual(len([t for t in available_types if t['requires_allocation']]), 1, "Only leave types with valid allocations should be returned.")

        self.assertNotIn(leave_type_no_allocation_no_country.id, available_ids,
                         "Duplicate leave types should filter out the leave with no country set.")
        self.assertIn(leave_type_no_allocation_belgium.id, available_ids,
                      "The Belgium-specific 'No Allocation' leave type should be available.")

        sequences = [t['sequence'] for t in available_types]
        self.assertEqual(sequences, sorted(sequences), "Available leave types should be sorted by sequence.")

        # Check available leave types when no employee is passed to the method (multiple employees selected in the Gantt view)
        # Only leave types that do not require allocation should be returned, since those are valid for all employees
        available_types_no_employee = self.env['hr.employee'].with_company(belgian_company).get_employee_available_leave_types()
        ids_no_employee = [t['id'] for t in available_types_no_employee]

        self.assertIn(leave_type_no_allocation_belgium.id, ids_no_employee,
                      "Leave types that do not require allocation should be returned even when no employee record is passed.")
        self.assertFalse([t for t in available_types_no_employee if t['requires_allocation']],
                         "No allocated leave types should be returned when no employee is passed.")

    def test_gantt_create_working_time_hour_full_duration_fully_flexible_centered(self):
        fully_flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Fully Flexible Calendar',
            'company_id': self.company.id,
            'calendar_type': 'undefined',
            'attendance_ids': [],
        })
        flexible_employee = self.env['hr.employee'].create({
            'name': 'Gantt Fully Flexible Employee',
            'company_id': self.company.id,
            'resource_calendar_id': fully_flexible_calendar.id,
        })
        working_time_type = self.env['hr.work.entry.type'].create({
            'name': 'Gantt Test Overtime (hour)',
            'code': 'GANTTTESTOVERTIME',
            'count_as': 'working_time',
            'request_unit': 'hour',
            'requires_allocation': False,
            'leave_validation_type': 'no_validation',
        })
        leave = self.env['hr.leave'].with_context(tracking_disable=True).create({
            'employee_id': flexible_employee.id,
            'work_entry_type_id': working_time_type.id,
            'request_date_from': date(2025, 3, 1),  # Saturday
            'request_date_to': date(2025, 3, 1),
            'request_duration': 'full',
            'number_of_hours': 8,
        })
        self.assertEqual(leave.request_hour_from, 8.0)
        self.assertEqual(leave.request_hour_to, 16.0)

    def test_gantt_create_absence_outside_schedule_dropped(self):
        employee = self.env['hr.employee'].create({
            'name': 'Gantt Outside Schedule Employee',
            'company_id': self.company.id,
            'resource_calendar_id': self.calendar_40h.id,
        })
        absence_type = self.env['hr.work.entry.type'].create({
            'name': 'Gantt Test Absence',
            'code': 'GANTTTESTABSENCE',
            'count_as': 'absence',
            'request_unit': 'day',
            'requires_allocation': False,
        })
        with patch.object(self.env.registry['bus.bus'], '_sendone') as mock_send:
            leaves = self.env['hr.leave'].with_context(
                tracking_disable=True,
                multi_create=True,
                leave_skip_date_check=True,
                multi_leave_request=True,
            ).create([{
                'employee_id': employee.id,
                'work_entry_type_id': absence_type.id,
                'request_date_from': date(2025, 3, 1),  # Saturday
                'request_date_to': date(2025, 3, 1),
            }])
            self.assertFalse(leaves.exists(), "the zero-duration absence should have been dropped")
            mock_send.assert_called_with(self.env.user, 'simple_notification', {
                'type': 'danger',
                'message': 'The time off is outside the working schedule of the employee',
            })

    def test_gantt_view_duration_based_schedule_with_leaves(self):
        """
        A duration-based-schedule leave of full day must gray out
        the whole day not just the amount of hours in the calendar
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
        self.jules_emp.write({'resource_calendar_id': duration_calendar.id})
        self.create_leave(date(2026, 3, 17), date(2026, 3, 18), employee_id=self.jules_emp.id).action_approve()

        unavailabilities = self.env['hr.leave']._gantt_unavailability(
            'employee_id',
            [self.jules_emp.id],
            datetime(2026, 3, 16, 0, 0, tzinfo=UTC),
            datetime(2026, 3, 20, 0, 0, tzinfo=UTC),
            'day',
        )
        user_tz = ZoneInfo(self.env.user.tz) if self.env.user.tz else UTC
        self.assertEqual(unavailabilities[self.jules_emp.id][0]['start'], datetime(2026, 3, 17, 0, 0, tzinfo=user_tz))
        self.assertEqual(unavailabilities[self.jules_emp.id][0]['stop'], datetime(2026, 3, 19, 0, 0, tzinfo=user_tz))

    def test_multi_create_encodes_hours_as_a_duration(self):
        """In the multi select context, the user can only encode durations for one or multiple days (splitted)"""
        worked_time = self.env['hr.work.entry.type'].create({
            'name': 'Worked Time',
            'code': 'WORKED_TIME',
            'count_as': 'working_time',
            'request_unit': 'hour',
            'requires_allocation': False,
        })
        leave = self.env['hr.leave'].with_context(default_employee_id=self.jules_emp.id)
        with Form(leave, view='hr_holidays_gantt.hr_leave_gantt_multi_create_view') as form:
            form.work_entry_type_id = worked_time
            self.assertFalse(form._get_modifier('number_of_hours', 'invisible'), "The duration is the only hour input.")
            self.assertTrue(form._get_modifier('request_hour_from', 'invisible'), "request_hour_from stays technical.")
            self.assertTrue(form._get_modifier('request_hour_to', 'invisible'), "request_hour_to stays technical.")
