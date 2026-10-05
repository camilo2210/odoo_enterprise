from datetime import UTC, datetime

from freezegun import freeze_time

from odoo import fields
from odoo.fields import Command, Domain
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestGetGanttData(TransactionCase):
    """Test the overridden get_gantt_data() function"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Scaffold & Co",
            },
        )
        # putting a "a" or "b" prefix helps with shuffling employees with and
        # without attendances together
        cls.attended_employees = cls.env['hr.employee'].create(
            [
                {
                    'name': f"{'a' if i else 'b'}Sir Attended {i}",
                    'company_id': cls.company.id,
                    'contract_date_start': '2025-10-01',
                }
                for i in range(19)
            ],
        )
        cls.env['hr.attendance'].create(
            [
                {
                    'employee_id': attended_employee.id,
                    'check_in': '2025-10-07 08:00:00',
                    'check_out': '2025-10-07 17:00:00',
                }
                for attended_employee in cls.attended_employees
            ],
        )
        cls.unattended_employees = cls.env['hr.employee'].create(
            [
                {
                    'name': f"{'a' if i else 'b'} Sir Unattended {i}",
                    'company_id': cls.company.id,
                    'contract_date_start': '2025-10-01',
                }
                for i in range(13)
            ],
        )
        # employee should never be shown as he is archived (it's the only way to
        # hide it by default on the gantt)
        cls.archived_employee = cls.env['hr.employee'].create(
            {
                'name': "Sir Archived",
                'company_id': cls.company.id,
                'contract_date_start': '2025-10-01',
                'active': False,
            },
        )
        cls.all_employees = cls.unattended_employees + cls.attended_employees
        cls.manager = cls.attended_employees[0]
        cls.employees_with_parent = (
            cls.unattended_employees[2:4] + cls.attended_employees[1:3]
        )
        for employee in cls.employees_with_parent:
            employee.parent_id = cls.manager

        # these datetime strings will be used in domains and parameters for get_gantt_data()
        cls.start_date = f'{datetime(2025, 10, 7, 0, 0, tzinfo=cls.env.tz).astimezone(UTC).replace(tzinfo=None)}'
        cls.stop_date = f'{datetime(2025, 10, 8, 0, 0, tzinfo=cls.env.tz).astimezone(UTC).replace(tzinfo=None)}'
        # All default parameters to be passed to get_gantt_data() to simulate
        # a real use-case
        cls.domain = Domain.AND([
            Domain('check_in', '<', cls.stop_date),
            Domain('check_out', '>', cls.start_date),
            Domain('employee_id.company_id', '=', cls.company.id),
        ])
        cls.groupby = ['employee_id']
        cls.read_specification = {
            'display_name': {},
            'check_in': {},
            'check_out': {},
            'employee_id': {'fields': {'display_name': {}}},
            'color': {},
        }
        cls.unavailability_fields = ['employee_id']
        cls.progress_bar_fields = ['employee_id']
        cls.scale = 'day'
        cls.context = cls.env.context.copy()
        cls.context['active_domain'] = [['employee_id.active', '=', True]]
        cls.context['allowed_company_ids'] = [cls.company.id]
        cls.context['user_domain'] = Domain.TRUE

    def _get_gantt_data_ids(
        self,
        offset: int,
        limit: int | None,
        user_domain: Domain,
    ) -> set[int]:
        """
        Wrapper for get_gantt_data() to remove repeated boilerplate
        """
        gantt_result = (
            self.env['hr.attendance']
            .with_context(**dict(self.context, user_domain=user_domain))
            .get_gantt_data(
                Domain(self.domain) & Domain(user_domain),
                self.groupby,
                self.read_specification,
                limit=limit,
                offset=offset,
                unavailability_fields=self.unavailability_fields,
                progress_bar_fields=self.progress_bar_fields,
                start_date=self.start_date,
                stop_date=self.stop_date,
                scale=self.scale,
            )
        )
        return {g['employee_id'][0] for g in gantt_result['groups']}

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

    def test_get_gantt_data_no_limit(self):
        """
        get_gantt_data() with no limit (None) should return all employees.
        Employees without attendances should be included in the return value
        based on some specific conditions.
        """
        # we want all employees without any filter
        returned_ids = self._get_gantt_data_ids(
            offset=0,
            limit=None,
            user_domain=[],
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.all_employees,
        )

    def test_get_gantt_data_no_limit_employee_fields(self):
        """
        Unattended employees should not be automatically filtered if domain is
        only about employee fields
        """
        returned_ids = self._get_gantt_data_ids(
            offset=0,
            limit=None,
            user_domain=[('employee_id.company_id', '=', self.company.id)],
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.all_employees,
        )

    def test_get_gantt_data_no_limit_related_fields(self):
        """
        Unattended employees should not be automatically filtered if domain is
        only about employee fields (even if it's a related field to employee_id)
        """
        # manager_id is related to employee_id.parent_id
        returned_ids = self._get_gantt_data_ids(
            offset=0,
            limit=None,
            user_domain=[('manager_id', '=', self.manager.id)],
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.employees_with_parent,
        )

    def test_get_gantt_data_no_limit_employee_id_int(self):
        """
        'employee_id' compared to an int should compare to their id
        """
        returned_ids = self._get_gantt_data_ids(
            offset=0,
            limit=None,
            user_domain=[('employee_id', '=', self.unattended_employees[2].id)],
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.unattended_employees[2],
        )

    def test_get_gantt_data_no_limit_employee_id_str(self):
        """
        'employee_id' compared to a string should compare to their name
        """
        returned_ids = self._get_gantt_data_ids(
            offset=0,
            limit=None,
            user_domain=[
                ('employee_id', '=', self.unattended_employees[2].name),
            ],
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.unattended_employees[2],
        )

    def test_get_gantt_data_no_limit_attendance_domain(self):
        """
        Unattended employees should not be in the return value since the field
        is not related to hr.employee
        """
        returned_ids = self._get_gantt_data_ids(
            offset=0,
            limit=None,
            user_domain=[('check_in', '>=', '2025-10-07 08:00:00')],
        )
        self._assert_returned_ids_equals_employee_list(
            returned_ids,
            self.attended_employees,
        )

    def _get_paginated_gantt_data_ids(
        self,
        limit: int,
        user_domain: Domain,
    ) -> list[set[int]]:
        """
        Will call get_gantt_data() repeatadly to simulate someone cycling though
        pages. The return value is the results of each page in order.
        """
        returned_ids = []
        offset = 0
        while True:
            page_ids = self._get_gantt_data_ids(
                offset=offset,
                limit=limit,
                user_domain=user_domain,
            )
            if not page_ids:
                break
            returned_ids.append(page_ids)
            offset += limit
        return returned_ids

    def _assert_paginated_returned_ids_equals_employee_list(
        self,
        returned_ids: list[set[int]],
        employees,
        limit: int,
    ) -> None:
        """
        Will compare 'returned_ids', returned form _get_paginated_gantt_data_ids
        to the 'employees' recordset passed as argument. The combination of all
        the pages result stored in returned_ids should be equal to employees.
        """
        employees = set(employees.mapped('id'))
        expected_pagination = [
            min(len(employees) - offset, limit)
            for offset in range(0, len(employees), limit)
        ]
        self.assertEqual(
            len(returned_ids),
            len(expected_pagination),
            f"get_gantt_data returned {len(returned_ids)} pages instead of {len(expected_pagination)}",
        )
        for i in range(len(expected_pagination)):
            self.assertEqual(
                len(returned_ids[i]),
                expected_pagination[i],
                f"Page n°{i} of get_gantt_data returned {len(returned_ids[i])} instead of {expected_pagination[i]} employees",
            )
            for employee_id in returned_ids[i]:
                self.assertIn(
                    employee_id,
                    employees,
                    f"Employee {employee_id} should not have been returned by get_gantt_data",
                )

    def test_get_gantt_data_limit(self):
        """
        get_gantt_data() should return a paginated result when a limit is
        applied. The offset it used to know on which page we are currently on.
        """
        limit = 5
        returned_ids = self._get_paginated_gantt_data_ids(
            limit,
            user_domain=[('employee_id.company_id.id', '=', self.company.id)],
        )
        self._assert_paginated_returned_ids_equals_employee_list(
            returned_ids,
            self.all_employees,
            limit,
        )

    def test_get_gantt_data_limit_n_of_attended_employees(self):
        """
        get_gantt_data()'s paginated result should still work even if limit is
        a divisor of the number of attended employees
        """
        limit = len(self.attended_employees)
        returned_ids = self._get_paginated_gantt_data_ids(limit, user_domain=[])
        self._assert_paginated_returned_ids_equals_employee_list(
            returned_ids,
            self.all_employees,
            limit,
        )

    def test_get_gantt_data_limit_over_attended_employees(self):
        """
        get_gantt_data()'s paginated result should still work even if limit is
        slightly over the number of attended employees
        """
        limit = len(self.attended_employees) + 2
        returned_ids = self._get_paginated_gantt_data_ids(limit, user_domain=[('employee_id.company_id.id', '=', self.company.id)])
        self._assert_paginated_returned_ids_equals_employee_list(
            returned_ids,
            self.all_employees,
            limit,
        )

    def test_get_gantt_data_limit_attendance_domain(self):
        """
        Unattended employees should not be displayed if user_domain contains
        attendance fields
        """
        limit = 5
        returned_ids = self._get_paginated_gantt_data_ids(
            limit,
            user_domain=[('check_in', '=', '2025-10-07 08:00:00')],
        )
        self._assert_paginated_returned_ids_equals_employee_list(
            returned_ids,
            self.attended_employees,
            limit,
        )

    def test_get_gantt_data_length_all_employees_5(self):
        """
        If user_domain does not filter an attendace field, then
        get_gantt_data()['length'] should also count employees without
        attendances
        Base case: page of length of 5
        """
        gantt_result = (
            self.env['hr.attendance']
            .with_context(**self.context)
            .get_gantt_data(
                self.domain,
                self.groupby,
                self.read_specification,
                limit=5,
                offset=10,  # should not change anything for 'length'
                unavailability_fields=self.unavailability_fields,
                progress_bar_fields=self.progress_bar_fields,
                start_date=self.start_date,
                stop_date=self.stop_date,
                scale=self.scale,
            )
        )
        self.assertEqual(
            gantt_result['length'],
            len(self.all_employees),
            "All employees should have been returned from get_gantt_data()['length']",
        )

    def test_get_gantt_data_length_all_employees_n_attended(self):
        """
        If user_domain does not filter an attendace field, then
        get_gantt_data()['length'] should also count employees without
        attendances
        Edge case: page length is the number of employees with attendances
        """
        gantt_result = (
            self.env['hr.attendance']
            .with_context(**self.context)
            .get_gantt_data(
                self.domain,
                self.groupby,
                self.read_specification,
                limit=len(self.attended_employees),
                offset=0,
                unavailability_fields=self.unavailability_fields,
                progress_bar_fields=self.progress_bar_fields,
                start_date=self.start_date,
                stop_date=self.stop_date,
                scale=self.scale,
            )
        )
        self.assertEqual(
            gantt_result['length'],
            len(self.all_employees),
            "All employees should have been returned from get_gantt_data()['length']",
        )

    def test_get_gantt_data_length_all_employees_no_limit(self):
        """
        If user_domain does not filter an attendace field, then
        get_gantt_data()['length'] should also count employees without
        attendances
        Base case: no limit
        """
        gantt_result = (
            self.env['hr.attendance']
            .with_context(**self.context)
            .get_gantt_data(
                self.domain,
                self.groupby,
                self.read_specification,
                limit=None,
                offset=0,
                unavailability_fields=self.unavailability_fields,
                progress_bar_fields=self.progress_bar_fields,
                start_date=self.start_date,
                stop_date=self.stop_date,
                scale=self.scale,
            )
        )
        self.assertEqual(
            gantt_result['length'],
            len(self.all_employees),
            "All employees should have been returned from get_gantt_data()['length']",
        )

    @freeze_time('2025-10-07')
    def test_get_gantt_data_unavailabilities(self):
        """
        Employees with (and without) attendances should both have assigned
        unavailabilites if they have a contract date start.
        This tests if the correct unavailabilites are set to each employees.
        """
        employees = {
            "unattended_cal_1": self.unattended_employees[0],
            "unattended_cal_2": self.unattended_employees[1],
            "attended_cal_1": self.attended_employees[0],
            "attended_cal_2": self.attended_employees[1],
        }

        # Employees need a contract to have unavailabilites
        for employee in employees.values():
            employee.current_version_id.contract_date_start = (
                fields.Date.today().replace(day=1)
            )

        calendar_templates = [
            {
                'name': 'Normal Calendar',
                'hour_from': 9,
                'hour_to': 17,
            },
            {
                'name': 'Extra Mile Calendar',
                'hour_from': 9,
                'hour_to': 20,
            },
        ]

        calendars = []
        for template in calendar_templates:
            calendars.append({
                'name': template['name'],
                'attendance_ids': [
                    Command.create(
                        {
                            'dayofweek': str(weekday),
                            'day_period': 'full_day',
                            'hour_from': template['hour_from'],
                            'hour_to': template['hour_to'],
                        },
                    )
                    for weekday in range(7)
                ],
                'company_id': self.company.id,
            })

        calendar_1, calendar_2 = self.env['resource.calendar'].create(calendars)

        calendar_map = {
            calendar_1: calendar_templates[0],
            calendar_2: calendar_templates[1],
        }

        employees['unattended_cal_1'].resource_calendar_id = calendar_1.id
        employees['unattended_cal_2'].resource_calendar_id = calendar_2.id
        employees['attended_cal_1'].resource_calendar_id = calendar_1.id
        employees['attended_cal_2'].resource_calendar_id = calendar_2.id

        gantt_result = (
            self.env['hr.attendance']
            .with_context(**self.context)
            .get_gantt_data(
                self.domain,
                self.groupby,
                self.read_specification,
                limit=None,
                offset=0,
                unavailability_fields=self.unavailability_fields,
                progress_bar_fields=self.progress_bar_fields,
                start_date=self.start_date,
                stop_date=self.stop_date,
                scale=self.scale,
            )
        )

        for employee in employees.values():
            self.assertIn(
                employee.id,
                gantt_result['unavailabilities']['employee_id'],
                f"{employee.name} should be present in gantt unavailabilities",
            )

            calendar = calendar_map[employee.resource_calendar_id]
            expected_unavailabilities = [
                {
                    'start': datetime(2025, 10, 7, 0, 0, tzinfo=self.env.tz).astimezone(UTC),
                    'stop': datetime(2025, 10, 7, calendar['hour_from'], 0, tzinfo=self.env.tz).astimezone(UTC),
                },
                {
                    'start': datetime(2025, 10, 7, calendar['hour_to'], 0, tzinfo=self.env.tz).astimezone(UTC),
                    'stop': datetime(2025, 10, 8, 0, 0, tzinfo=self.env.tz).astimezone(UTC),
                },
            ]

            self.assertEqual(
                expected_unavailabilities,
                gantt_result['unavailabilities']['employee_id'][employee.id],
                f"{employee.name} did not have the expected unavailabilites",
            )
