# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from dateutil.relativedelta import relativedelta

from odoo.fields import Command
from odoo.tests import tagged
from odoo.addons.l10n_be_hr_payroll.tests.common import TestPayrollCommon


@tagged('-at_install', 'post_install', 'post_install_l10n')
class TestCP302ThirteenMonth(TestPayrollCommon):
    """
    Test the computation of the 13th month for personnel under the joint
    commitee 302 (CP302). Specifically, test the return value of the
    payslip._cp302_get_paid_amount_13th_month() function.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        belgian_tz = 'Europe/Brussels'
        cls.env.user.tz = belgian_tz
        cls.belgian_company.tz = belgian_tz
        cls.env.company.current_payroll_config_id.l10n_be_employer_category_id = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00017').id
        cls.belgian_company.current_payroll_config_id.l10n_be_employer_category_id = cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00017').id

        # belgian_company_id.resource_calendar_id has an incorrect 40hrs/week
        # calendar, so I redefine it here
        cls.resource_calendar_40 = cls.env['resource.calendar'].create({
            'name': 'Standard 40h/week',
            'company_id': cls.belgian_company.id,
            'full_time_required_hours': 40,
            'attendance_ids': [
                Command.create({'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                Command.create({'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                Command.create({'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                Command.create({'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                Command.create({'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
            ],
        })
        # cls.resource_calendar has not defined hours, so I make a new calendar
        cls.resource_calendar_38 = cls.env['resource.calendar'].create({
            'name': 'Standard 38h/week',
            'company_id': cls.belgian_company.id,
            'full_time_required_hours': 38,
            'attendance_ids': [
                Command.create({'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                Command.create({'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                Command.create({'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                Command.create({'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                Command.create({'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6}),
            ],
        })
        # resource_calendar_mid_time ends at 16.5, my tests test with this one,
        # which is slightly more than half (employee still finishes at 16.6)
        cls.resource_calendar_38_half = cls.env['resource.calendar'].create({
            'name': 'Calendar (Mid-Time)',
            'company_id': cls.belgian_company.id,
            'full_time_required_hours': 38,
            'attendance_ids': [
                Command.create({'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                Command.create({'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                Command.create({'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                Command.create({'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
            ],
        })

        cls.belgian_company.resource_calendar_id = cls.resource_calendar_40

        cls.cp200_struct = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.cp302 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_302')

        cls.sick_leave_codes = [
            '013.00',  # Congé maladie
            '123.00',  # Maladie de longue durée
            '122.00',  # days of illness after 30th day
        ]
        cls.maternity_leave_codes = [
            '128.00',  # Congé maternité
            '128.04',  # Maternity leave or maternity leave converted in the event of death or hospitalization of the mother
        ]
        cls.compelling_reason_codes = [
            '020.20',  # Justified Reason (Paid)
            '154.00',  # Justified Reason (Unpaid)
            '135.00',  # Unpredictable Reason (Unpaid)
        ]
        cls.paternity_leave_codes = [
            '007.05',  # Congé de paternité (Payé par la société)
            '128.05',  # Congé de paternité (Légal)
        ]
        cls.military_reserve_codes = [
            '150.00',  # Militia obligation (Unpaid)
        ]

    @classmethod
    def _create_leave_from_we_type_code(
        cls, employee, work_entry_type_code, date_from, date_to=False,
        # to specify half days
        half_day_period_from="am", half_day_period_to="pm",
    ):
        """
        Creates a leave on the desired period, with a work entry type with the
        given code. If the work entry type does not exist it will create it.
        `half_day_period_from` and `half_day_period_to` are used to specify
        half-day leaves
        """
        is_half_day = half_day_period_from == 'pm' or half_day_period_to == 'am'

        work_entry_type = cls.env['hr.work.entry.type'].search([
            ['code', '=', work_entry_type_code],
            ['country_id', '=', cls.env.ref('base.be').id],
        ])
        if not work_entry_type:
            # wanted work entry type does not exist. Let's create one
            work_entry_type = cls.env['hr.work.entry.type'].create({
                'name': f'Work Entry Type for code {work_entry_type_code}',
                'code': work_entry_type_code,
                'requires_allocation': False,
                'request_unit': 'half_day' if is_half_day else 'day',
                'country_id': cls.env.ref('base.be').id,
            })
        # to avoid making time-consuming errors
        if work_entry_type.request_unit != 'half_day' and is_half_day:
            raise Exception(
                f"Cannot put half day for work entry type {work_entry_type.name}"
                f" of request_unit of {work_entry_type.request_unit}",
            )
        if work_entry_type.requires_allocation:
            # make sure enough days are allocated to put the leave
            cls.env['hr.leave.allocation'].create({
                'name': f'Allocation from {date_from} to {date_to}',
                'work_entry_type_id': work_entry_type.id,
                'employee_id': employee.id,
                'number_of_days': (date_to - date_from).days + 1,
                'date_from': '1970-01-01',
                'state': 'confirm',
            }).action_approve()
        return cls.env['hr.leave'].create({
            'employee_id': employee.id,
            'work_entry_type_id': work_entry_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'request_date_from_period': half_day_period_from,
            'request_date_to_period': half_day_period_to,
        })

    @classmethod
    def _get_day_count_in_period(cls, date_from, date_to) -> dict[str, int]:
        """
        Returns count of week days for a given date range in this format:
        {'monday': 53, 'tuesday': 52, etc.}
        This is useful to guess the number working days in the year.
        """
        weekday_counts = defaultdict(int)
        for year in range(date_from.year, date_to.year + 1):
            month_from = date_from.month if year == date_from.year else 1
            month_to = date_to.month if year == date_to.year else 12
            for month in range(month_from, month_to + 1):
                month_calendar = calendar.monthcalendar(year, month)
                for week in month_calendar:
                    for weekday, day in enumerate(week):
                        if day == 0:  # not part of current month
                            continue
                        day = date(year, month, day)
                        if not (date_from <= day <= date_to):
                            # not part of given date range
                            continue
                        day_name = calendar.day_name[weekday].lower()
                        weekday_counts[day_name] += 1
        return dict(weekday_counts)

    @classmethod
    def _get_week_day_count_in_period(cls, date_from, date_to) -> dict[str, int]:
        days_in_range = cls._get_day_count_in_period(date_from, date_to)
        days_in_range.pop('saturday', None)
        days_in_range.pop('sunday', None)
        return days_in_range

    def test_monthly_full_year(cls):
        employee = cls.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 10, 3),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': cls.cp302.id,
            'resource_calendar_id': cls.resource_calendar_38.id,
            'lang': 'fr_BE',
        })
        payslip = cls.env['hr.payslip'].create({
            'name': "Payslip Test",
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": cls.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        cls.assertAlmostEqual(amount, employee.wage, """
Personnel paid monthly that worked the whole year, should have a gross 13th
month equal to their latest monthly salary.
        """)

    def test_hourly_full_year(self):
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 10, 3),
            'contract_date_end': False,
            'wage_type': 'hourly',
            'hourly_wage': 20,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
            'lang': 'fr_BE',
        })
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        wanted_amount = round(employee.hourly_wage * employee.version_id.resource_calendar_id.hours_per_week * (4 + 1 / 3), 2)
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Personnel paid hourly that worked the whole year, should have a gross 13th month
equal to 4.333... weeks of pay of their hourly wage
        """)

    def test_employee_part_time_monthly_full_year(self):
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 10, 3),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38_half.id,
            'lang': 'fr_BE',
        })
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
Personnel with a part time contract (19.2h) should have a 13th month equal to
their monthly wage if they are paid monthly and if they worked the whole year
        """)

    def test_employee_part_time_hourly_full_year(self):
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 10, 3),
            'contract_date_end': False,
            'hourly_wage': 20,
            'wage_type': 'hourly',
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38_half.id,
            'lang': 'fr_BE',
        })
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        # hourly wage * hours per week * 4.333 (number of weeks per month as per
        # the joint committee)
        wanted_amount = round(20 * 19.2 * (4 + 1 / 3), 2)
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Personnel with a part time contract (19.2h) should have a 13th month equal to
4.333 weeks of wage if they are paid hourly and if they worked the whole year
        """)

    def test_unpaid_leaves_half_days(self):
        """
        Proratisation should still work correctly with half days
        e.g.: do not count 1.5 days of unassimilated time as 2 full days but
        rather as a per-hour proratization
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 10, 3),
            'contract_date_end': False,
            'wage_type': 'hourly',
            'hourly_wage': 10,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code='test_unpaid',
            date_from=date(2025, 2, 4),  # tuesday
            date_to=date(2025, 2, 5),  # wednesday
            half_day_period_from='pm',
            half_day_period_to='pm',
        )

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })

        workable_days = sum(
            self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 12, 31)).values(),
        )
        max_hours_per_year = workable_days * 8
        # 1.5 days are unpaid (i.e.: unassimilated)
        hours_worked = (workable_days - 1.5) * 8
        assimilated_days_ratio = hours_worked / max_hours_per_year
        max_13th_month = employee.hourly_wage * employee.version_id.resource_calendar_id.hours_per_week * (4 + 1 / 3)
        wanted_amount = round(max_13th_month * assimilated_days_ratio, 2)

        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A worker with a day and half of unassimilated leaves shoud have its 13th month
value slightly reduced due to proratization
        """)

    def test_always_assimilable_leaves(self):
        """
        Some leave types are always assimilated (i.e.: always counted in the
        13th month)
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 10, 3),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38_half.id,
            'lang': 'fr_BE',
        })

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code='016.00',  # paid legal leave
            date_from=date(2025, 2, 2),
            date_to=date(2025, 3, 4),
        )
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code='019.00',  # Repos compensatoire (récupération)
            date_from=date(2025, 4, 1),
            date_to=date(2025, 4, 1),
        )
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code='011.00',  # extra-legal leave
            date_from=date(2025, 6, 3),
            date_to=date(2025, 8, 2),
        )

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })

        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
Leaves that are always assimilated should not decrease the 13th month
        """)

    def test_limited_calendar_assimilable_leaves(self):
        """
        Some work entries are limited, not per fixed amount of days per year,
        but rather per calendar period per uninterrupted work entry range.
        Per the documentation, it's maternity leaves and military service.
        As we don't have a work entry type for the military service, only the
        maternity leaves will be tested.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 3, 3),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })

        calendar_week = timedelta(days=7)
        calendar_day = timedelta(days=1)

        # maternity leaves will be used. They are limited up to 15 calendar
        # weeks per period
        for leave in [
            # last year. Should not be counted
            {
                'code': self.maternity_leave_codes[0],
                'start': date(2024, 5, 2),
                'stop': date(2024, 5, 10),
            },
            # last year but adjacent to the next leave. Should reduce the next
            # maternity leave's limit by 4 weeks and one day
            {
                'code': self.maternity_leave_codes[1],
                'start': date(2024, 12, 31) - 4 * calendar_week,
                'stop': date(2024, 12, 31),
            },
            # only 11 weeks should be assimilated (15 - 4 weeks)
            {
                'code': self.maternity_leave_codes[0],
                'start': date(2025, 1, 1),
                'stop': date(2025, 1, 1) + 20 * calendar_week,
            },
            # only 15 weeks should be assimilated
            {
                'code': self.maternity_leave_codes[1],
                'start': date(2025, 6, 2),
                'stop': date(2025, 6, 2) + 16 * calendar_week,
            },
            # 6 days should be assimilated
            {
                'code': self.maternity_leave_codes[1],
                'start': date(2025, 12, 25),
                'stop': date(2026, 2, 1),
            },
        ]:
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=leave['code'],
                date_from=leave['start'],
                date_to=leave['stop'],
            )

        # part of the leaves that went over the limit
        non_assimilable_ranges = [
            {
                # -1 day as the period started with - 4 weeks
                'start': date(2025, 1, 1) + 11 * calendar_week - calendar_day,
                'stop': date(2025, 1, 1) + 20 * calendar_week,
            },
            {
                'start': date(2025, 6, 2) + 15 * calendar_week,
                'stop': date(2025, 6, 2) + 16 * calendar_week,
            },
        ]

        # count the days that were supposed to be prestated, but were
        # unassimilated instead
        non_assimilable_work_days = 0
        for range in non_assimilable_ranges:
            week_days_in_range = self._get_week_day_count_in_period(range['start'], range['stop'])
            non_assimilable_work_days += sum(week_days_in_range.values())

        workable_days = sum(
            self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 12, 31)).values(),
        )
        assimilated_days = workable_days - non_assimilable_work_days
        worked_days_ratio = assimilated_days / workable_days
        wanted_amount = round(employee.wage * worked_days_ratio, 2)

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertAlmostEqual(amount, wanted_amount, msg="""
Got an unexpected cp302 13th month amount when putting many maternal leave
periods that should be limited by a calendar period of 15 consecutive weeks.
        """)

    def test_yearly_limited_assimilable_leaves(self):
        """
        Some work entries are limited by a certain amount of days per year.
        The limit applies per category of work entry type, and not per work
        entry type code.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 3, 3),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })

        # the following leave categories will be used:
        # - compelling_reason (10 day limit)
        # - paternity_leave (10 day limit)
        # - military_reserve_call (74 day limit)
        for leave in [
            # 0 working day in current year
            {
                'code': self.paternity_leave_codes[0],
                'start': date(2024, 3, 1),
                'stop': date(2024, 3, 10),
            },
            # 2 working days current in year
            {
                'code': self.compelling_reason_codes[0],
                'start': date(2024, 12, 25),
                'stop': date(2025, 1, 3),
            },
            # 3 working days
            {
                'code': self.paternity_leave_codes[0],
                'start': date(2025, 1, 31),
                'stop': date(2025, 2, 4),
            },
            # 51 working days
            {
                'code': self.military_reserve_codes[0],
                'start': date(2025, 2, 5),
                'stop': date(2025, 4, 9),
            },
            # 4 working days
            {
                'code': self.compelling_reason_codes[1],
                'start': date(2025, 4, 10),
                'stop': date(2025, 4, 15),
            },
            # 14 working days - 7 are unassimilated
            {
                'code': self.paternity_leave_codes[1],
                'start': date(2025, 5, 20),
                'stop': date(2025, 6, 5),
            },
            # 41 working days - 18 are unassimilated
            {
                'code': self.military_reserve_codes[0],
                'start': date(2025, 6, 6),
                'stop': date(2025, 8, 1),
            },
            # 5 working days - 1 is unassimilated
            {
                'code': self.compelling_reason_codes[0],
                'start': date(2025, 10, 1),
                'stop': date(2025, 10, 7),
            },
            # 4 working days - 4 is unassimilated
            {
                'code': self.compelling_reason_codes[2],
                'start': date(2025, 11, 5),
                'stop': date(2025, 11, 10),
            },
        ]:
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=leave['code'],
                date_from=leave['start'],
                date_to=leave['stop'],
            )

        # we'll now count all the working covered by the leaves, then compute
        # the number of days above the limit of the work entry type code category
        unassimilated_days = 0

        this_year_paternity_leaves = [
            {
                'start': date(2025, 1, 31),
                'stop': date(2025, 2, 4),
            },
            {
                'start': date(2025, 5, 20),
                'stop': date(2025, 6, 5),
            },
        ]
        this_year_paternity_leave_days = 0
        for range in this_year_paternity_leaves:
            week_days = self._get_week_day_count_in_period(range['start'], range['stop'])
            this_year_paternity_leave_days += sum(week_days.values())

        unassimilated_days += max(0, this_year_paternity_leave_days - 10)

        this_year_compelling_reason = [
            {
                # we don't count the leaves in the previous year
                'start': date(2025, 1, 1),
                'stop': date(2025, 1, 3),
            },
            {
                'start': date(2025, 4, 10),
                'stop': date(2025, 4, 15),
            },
            {
                'start': date(2025, 10, 1),
                'stop': date(2025, 10, 7),
            },
            {
                'start': date(2025, 11, 5),
                'stop': date(2025, 11, 10),
            },
        ]
        this_year_compelling_reason_days = 0
        for range in this_year_compelling_reason:
            week_days = self._get_week_day_count_in_period(range['start'], range['stop'])
            this_year_compelling_reason_days += sum(week_days.values())

        unassimilated_days += max(0, this_year_compelling_reason_days - 10)

        this_year_military_reserve = [
            {
                'start': date(2025, 2, 5),
                'stop': date(2025, 4, 9),
            },
            {
                'start': date(2025, 6, 6),
                'stop': date(2025, 8, 1),
            },
        ]
        this_year_military_reserve_days = 0
        for range in this_year_military_reserve:
            week_days = self._get_week_day_count_in_period(range['start'], range['stop'])
            this_year_military_reserve_days += sum(week_days.values())

        unassimilated_days += max(0, this_year_military_reserve_days - 74)

        # proratization
        workable_days = sum(
            self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 12, 31)).values(),
        )
        assimilated_days = workable_days - unassimilated_days
        worked_days_ratio = assimilated_days / workable_days
        wanted_amount = round(employee.wage * worked_days_ratio, 2)

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertAlmostEqual(amount, wanted_amount, msg="""
Got an unexpected cp302 13th month amount when putting many different yearly
limited leaves.
        """)

    def test_long_sick_leave(self):
        """
        Max six consecutive months of sick leave can be assimilated at a rate of
        50% for any sick leave period >= 6 months
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2025, 2, 3),
            date_to=date(2025, 10, 31),
        )

        # only the first six months are assimilated at 50%
        work_days_in_six_months_leave = sum(self._get_week_day_count_in_period(
            date(2025, 2, 3), date(2025, 2, 3) + relativedelta(months=6, days=-1)
        ).values())
        # the rest isn't assimilated
        unassimilated_work_days_in_leave = sum(self._get_week_day_count_in_period(
            date(2025, 2, 3) + relativedelta(months=6),
            date(2025, 10, 31),
        ).values())

        workable_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 12, 31),
        ).values())
        assimilated_days = workable_days - work_days_in_six_months_leave * 0.5 - unassimilated_work_days_in_leave
        wanted_amount = round(employee.wage * (assimilated_days / workable_days), 2)

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertAlmostEqual(amount, wanted_amount, msg="""
6 months of sick leave should be assimilated at a rate of 50% for a single
sick leave period >= 6 months in one year
        """)

    def test_long_sick_leave_cross_year(self):
        """
        If a long sick leave period is over two different years, than we should
        shrink the period to max 6 months, then see how many days are still in
        the current year and then assimilate those days at a rate of 50%
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2024, 9, 1),
            date_to=date(2025, 3, 31),
        )

        # only the days in this year are assimilable
        work_days_during_leave = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 3, 31),
        ).values())

        workable_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 12, 31),
        ).values())
        assimilated_days = workable_days - work_days_during_leave * 0.5
        wanted_amount = round(employee.wage * (assimilated_days / workable_days), 2)

        payslip_2025 = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip_2025.compute_sheet()
        amount = payslip_2025.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertAlmostEqual(amount, wanted_amount, msg="""
Days in the current year of sick leave periods longer than 6 months should
still be 50% assimilable even if the period is cross-year.
        """)

        # prolong the sick leave period over six months
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[1],
            date_from=date(2025, 4, 1),
            date_to=date(2025, 8, 1),
        )

        assimilated_leave_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 1, 1) + relativedelta(months=6, days=-1)
        ).values())
        work_days_during_leave = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 8, 1),
        ).values())
        unassimilated_days = work_days_during_leave - assimilated_leave_days * 0.5
        assimilated_days = workable_days - unassimilated_days

        wanted_amount = round(employee.wage * (assimilated_days / workable_days), 2)
        payslip_2025.compute_sheet()
        amount = payslip_2025.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Days in the current year of sick leave periods longer than 6 months should
still be 50% assimilable even if the period is cross-year, any sick day over
that period should not be assimilated
        """)

        # prolong the sick leave period over a year
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2025, 8, 2),
            date_to=date(2025, 11, 30),
        )

        # six months should still be assimilated because the leave period is too
        # short to be assimilated in 2024
        work_days_during_leave = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 11, 30),
        ).values())
        assimilated_leave_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 1, 1) + relativedelta(months=6, days=-1)
        ).values())
        unassimilated_days = work_days_during_leave - assimilated_leave_days * 0.5
        assimilated_days = workable_days - unassimilated_days
        wanted_amount = round(employee.wage * (assimilated_days / workable_days), 2)

        payslip_2025.compute_sheet()
        amount = payslip_2025.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertAlmostEqual(amount, wanted_amount, msg="""
A long sick leave period not assimilated in the previous year can be assimilated
even if that period is longer than a year
        """)

        # let's make sure that the leave is NOT assimilated in 2024
        payslip_2024 = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        work_days_2024 = sum(self._get_week_day_count_in_period(
            date(2024, 1, 1), date(2024, 12, 31),
        ).values())
        leave_days_2024 = sum(self._get_week_day_count_in_period(
            date(2024, 9, 1), date(2024, 12, 31),
        ).values())
        assimilated_days = work_days_2024 - leave_days_2024
        wanted_amount = round(employee.wage * (assimilated_days / work_days_2024), 2)
        payslip_2024.compute_sheet()
        amount = payslip_2024.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A leave cannot be assimilated if, in the current year, it is less than six
months. Even if the leave is longer when including future years.
        """)

        # making the leave long enough so that it's assimilated in 2024
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[1],
            date_from=date(2024, 4, 1),  # monday
            date_to=date(2024, 8, 31),
        )

        # let's make sure that the leave is assimilated in 2024
        assimilable_leave_days_2024 = sum(self._get_week_day_count_in_period(
            date(2024, 4, 1), date(2024, 4, 1) + relativedelta(months=6, days=-1)
        ).values())
        leave_days_2024 = sum(self._get_week_day_count_in_period(
            date(2024, 4, 1), date(2024, 12, 31),
        ).values())
        unassimilated_days = leave_days_2024 - assimilable_leave_days_2024 * 0.5
        assimilated_days = work_days_2024 - unassimilated_days
        wanted_amount = round(employee.wage * (assimilated_days / work_days_2024), 2)
        payslip_2024.compute_sheet()
        amount = payslip_2024.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A long sick leave period should be assimilated in the first year that is covered
by it by more than 6 months. Even if the sick leave period is longer than a year
        """)

        # the leave has been assimilated in 2024, since it's longer than a year,
        # we cannot assimilate it again in 2025
        work_days_during_leave = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 11, 30),
        ).values())
        assimilated_days = workable_days - work_days_during_leave
        wanted_amount = round(employee.wage * (assimilated_days / workable_days), 2)
        payslip_2025.compute_sheet()
        amount = payslip_2025.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        self.assertAlmostEqual(amount, wanted_amount, msg="""
If a sick leave period >= 1 year was already assimilated in the previous year,
then it cannot be reassimilated into the current year again.
        """)

    def test_assimilable_hours_after_contract(self):
        """
        If the employee is fired, or resigns early in the year, then some days
        after the contract end until the end of the year are still assimilated
        """
        work_days_2025 = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), date(2025, 12, 31),
        ).values())
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })
        departures_reasons = {
            'dead': self.env.ref('hr.departure_dead'),
            'resigned_retired': self.env.ref('hr.departure_retired'),
            'resigned_anitcipated_retirement': self.env.ref('l10n_be_hr_payroll.departure_resigned_anticipated_retirement'),
            'fired_early_retirement': self.env.ref('l10n_be_hr_payroll.departure_fired_early_retirement'),
            # should not assimilate days after contract end
            'fired': self.env.ref('hr.departure_fired'),
        }

        employee.departure_reason_id = departures_reasons['fired']
        employee.departure_date = date(2025, 5, 15)
        worked_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), employee.departure_date,
        ).values())
        wanted_amount = round(employee.wage * (worked_days / work_days_2025), 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 5, 1),
            "date_to": date(2025, 5, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A fired employee should not receive assimilated days after the departure date
        """)

        employee.departure_reason_id = departures_reasons['dead']
        employee.departure_date = date(2025, 5, 15)
        worked_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), employee.departure_date,
        ).values())

        assimilated_days_after_contract = sum(self._get_week_day_count_in_period(
            employee.departure_date, employee.departure_date + relativedelta(months=6)
        ).values())
        assimilated_days = worked_days + assimilated_days_after_contract
        wanted_amount = round(employee.wage * (assimilated_days / work_days_2025), 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 5, 1),
            "date_to": date(2025, 5, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Max six months after the departure date can be assimilated for dead personnel
        """)

        employee.departure_reason_id = departures_reasons['resigned_retired']
        employee.departure_date = date(2025, 5, 15)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 5, 1),
            "date_to": date(2025, 5, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
All days after the end of the contract are assimilated for retired personnel
        """)

        employee.departure_reason_id = departures_reasons['resigned_anitcipated_retirement']
        employee.departure_date = date(2025, 5, 15)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 5, 1),
            "date_to": date(2025, 5, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
All days after the end of the contract are assimilated for personnel on
anticipated retirement
        """)

        employee.departure_reason_id = departures_reasons['fired_early_retirement']
        employee.departure_date = date(2025, 5, 15)
        worked_days = sum(self._get_week_day_count_in_period(
            date(2025, 1, 1), employee.departure_date,
        ).values())
        assimilated_days_after_contract = sum(self._get_week_day_count_in_period(
            employee.departure_date, date(2025, 12, 31),
        ).values())
        assimilated_days = worked_days + assimilated_days_after_contract * 0.2
        wanted_amount = round(employee.wage * (assimilated_days / work_days_2025), 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 5, 1),
            "date_to": date(2025, 5, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
All days after the contract for personnel fired to early retirement must be
assimilated at a rate of 20%
        """)

    def test_can_get_13th_month(self):
        """
        Under certain conditions, employees cannot get their 13th month at all
        """
        departure_reasons = {
            'resigned': self.env.ref('hr.departure_resigned'),
            'fired': self.env.ref('hr.departure_fired'),
            'fired_serious_misconduct': self.env.ref('l10n_be_hr_payroll.departure_fired_serious_misconduct'),
            'resigned_serious_employer_misconduct': self.env.ref('l10n_be_hr_payroll.departure_resigned_serious_employer_misconduct'),
            'resigned_force_majeure': self.env.ref('l10n_be_hr_payroll.departure_resigned_force_majeure'),
            'resigned_retired': self.env.ref('hr.departure_retired'),
            'resigned_anitcipated_retirement': self.env.ref('l10n_be_hr_payroll.departure_resigned_anticipated_retirement'),
            # prépension
            'fired_early_retirement': self.env.ref('l10n_be_hr_payroll.departure_fired_early_retirement'),
        }

        work_days_2024 = sum(self._get_week_day_count_in_period(
            date(2024, 1, 1), date(2024, 12, 31),
        ).values())
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2023, 12, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })
        employee_flx = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2024, 3, 31),
            'l10n_be_flexi_monthly_wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_40.id,
            'lang': 'fr_BE',
        })
        employee_flx.version_id.l10n_be_dimona_category = 'flx'

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2023, 12, 1),
            "date_to": date(2023, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Employees with less than 2 months of seniority cannot get their 13th month
        """)

        employee.departure_date = date(2024, 1, 31)
        worked_days = sum(self._get_week_day_count_in_period(
            date(2024, 1, 1), date(2024, 1, 31),
        ).values())
        wanted_amount = round((worked_days / work_days_2024) * employee.wage, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 1, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Employees with 2 months of seniority can get their 13th month
        """)

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee_flx.id,
            'version_id': employee_flx.version_id.id,
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 1, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Flexi Job employees (dimona == 'flx') with less than 2 months of seniority
cannot get their 13th month.
        """)

        employee_flx.departure_date = date(2024, 3, 31)
        worked_days = sum(self._get_week_day_count_in_period(
            date(2024, 1, 1), date(2024, 3, 31),
        ).values())
        wanted_amount = round((worked_days / work_days_2024) * employee_flx.l10n_be_flexi_monthly_wage, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee_flx.id,
            'version_id': employee_flx.version_id.id,
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 3, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Flexi Job (dimona == 'flx') employees with 2 months of seniority can get their
13th month.
        """)

        employee.departure_reason_id = departure_reasons['resigned_force_majeure']
        # less than 2 months worked in year because february is 29 days
        employee.departure_date = date(2024, 2, 29)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 2, 1),
            "date_to": date(2024, 2, 29),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Employees that resign for force majeure cannot get their 13th month if they have
a seniority shorter than 2 months in the year
        """)

        employee.departure_reason_id = departure_reasons['resigned_force_majeure']
        # now more than 2 months have been worked in the year
        employee.departure_date = date(2024, 3, 15)
        worked_days = sum(self._get_week_day_count_in_period(
            date(2024, 1, 1), date(2024, 3, 15),
        ).values())
        wanted_amount = round((worked_days / work_days_2024) * employee.wage, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 3, 1),
            "date_to": date(2024, 3, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
Employees that resign for force majeure can get their 13th month if they have a
seniority >= 2 months in the year
        """)

        employee.departure_reason_id = departure_reasons['resigned']
        employee.departure_date = date(2024, 12, 30)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Resigned employees cannot get their 13th month if their departure date is before
the end of the year
        """)

        employee.departure_reason_id = departure_reasons['resigned']
        employee.departure_date = date(2024, 12, 31)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
Resigned employees can get their 13th month if their departure date is at the
end of the year, or after.
        """)

        employee.departure_reason_id = departure_reasons['fired_serious_misconduct']
        employee.departure_date = date(2024, 12, 31)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Employees fired for "faute grave" cannot get their 13th month
        """)

        employee.version_id.fixed_term = True
        employee.departure_reason_id = False
        employee.departure_date = False
        employee.contract_date_end = date(2024, 12, 31)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
CDD employees can get their 13th month if their contract does not end sooner
than expected
        """)

        employee.version_id.fixed_term = True
        employee.departure_reason_id = departure_reasons['resigned_force_majeure']
        employee.departure_date = date(2024, 12, 31)
        employee.contract_date_end = date(2024, 12, 31)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, employee.wage, msg="""
CDD employees can get their 13th month if their contract does not end sooner
than expected, even if there is a departure reason
        """)

        employee.version_id.fixed_term = True
        employee.departure_reason_id = departure_reasons['resigned_force_majeure']
        employee.departure_date = date(2024, 12, 30)
        employee.contract_date_end = date(2024, 12, 31)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
CDD employees cannot get their 13th month if their contract ends sooner than expected.
        """)

        employee.l10n_be_dimona_category = 'stu'
        employee.version_id.fixed_term = False
        employee.departure_reason_id = False
        employee.departure_date = False
        employee.contract_date_end = False
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Students (dimona == 'stu') should never receive a 13th month.
        """)

    def test_different_consecutive_versions(self):
        """
        The 13th month computation should be based on the current version of the
        payslip, even if the employee changes versions in the year.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2023, 1, 1),
            'wage_type': 'hourly',
            'hourly_wage': 10,
            'wage': 0,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38_half.id,
            'lang': 'fr_BE',
        })

        version_1 = employee.version_id
        version_2 = employee.create_version({
            'date_version': date(2024, 6, 17),  # monday
            'wage_type': 'monthly',
            'wage': 4000,
            'resource_calendar_id': self.resource_calendar_40.id,
        })

        days_2023 = self._get_day_count_in_period(date(2023, 1, 1), date(2023, 12, 31))
        days_2024 = self._get_day_count_in_period(date(2024, 1, 1), date(2024, 12, 31))

        # 3 whole weeks
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2023, 5, 1),  # monday
            date_to=date(2023, 5, 19),  # friday
        )
        # 2 whole weeks
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2024, 6, 3),  # monday
            date_to=date(2024, 6, 16),  # friday
        )
        # 1 whole week
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2024, 6, 17),  # monday
            date_to=date(2024, 6, 21),  # friday
        )

        workable_hours_2023 = (days_2023['monday'] + days_2023['tuesday']) * 7.6 + days_2023['wednesday'] * 4
        hours_per_week = version_1.resource_calendar_id.hours_per_week
        unassimilated_hours = hours_per_week * 3
        full_13th_month = version_1.hourly_wage * hours_per_week * (4 + 1 / 3)
        wanted_amount = round(full_13th_month * (workable_hours_2023 - unassimilated_hours) / workable_hours_2023, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': version_1.id,
            "date_from": date(2023, 12, 1),
            "date_to": date(2023, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
When computing the 13th month of an employee on a version that is not its latest,
the computation should use the correct payslip's version_id.
        """)

        workable_hours_2024 = (days_2024['monday'] + days_2024['tuesday']) * 7.6 + days_2024['wednesday'] * 4
        days_up_to_may = self._get_day_count_in_period(date(2024, 1, 1), date(2024, 5, 31))
        worked_hours = (days_up_to_may['monday'] + days_up_to_may['tuesday']) * 7.6 + days_up_to_may['wednesday'] * 4
        full_13th_month = version_1.hourly_wage * hours_per_week * (4 + 1 / 3)
        wanted_amount = round(full_13th_month * (worked_hours / workable_hours_2024), 2)
        employee.departure_date = date(2024, 5, 31)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': version_1.id,
            "date_from": date(2024, 5, 1),
            "date_to": date(2024, 5, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
When computing the 13th month of an employee on a version that is not its latest,
the computation should use the correct payslip's version_id.
Even if another version in the same year is defined after the payslip.
        """)

        # the leave period is on the version change. So let's count them all separately
        week_days_before_leave = self._get_week_day_count_in_period(date(2024, 1, 1), date(2024, 6, 2))
        week_days_after_leave = self._get_week_day_count_in_period(date(2024, 6, 22), date(2024, 12, 31))
        hours_worked_as_part_time = 7.6 * (week_days_before_leave['monday'] + week_days_before_leave['tuesday']) + 4 * week_days_before_leave['wednesday']
        hours_worked_as_full_time = sum(week_days_after_leave.values()) * 8
        assimilated_hours = hours_worked_as_part_time + hours_worked_as_full_time

        employee.departure_date = False
        week_days_2024 = sum(self._get_week_day_count_in_period(date(2024, 1, 1), date(2024, 12, 31)).values())
        workable_hours_2024 = week_days_2024 * 8
        wanted_amount = round(version_2.wage * (assimilated_hours / workable_hours_2024), 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': version_2.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
When computing the 13th month at the end of the year, and, during the year, the
employee changes version, then the computation should be based on the latest
version.
e.g.: if the employee goes from part time to full time, then he should not get
      its full 13th month as he worked less time during the previous version
      than we he can now with the current version.
        """)

    def test_mixed_leaves_part_time(self):
        """
        Test for a practical use case of a part time employee with an hourly
        wage that has multiple leave types
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2023, 6, 15),
            'contract_date_end': False,
            'hourly_wage': 10,
            'wage_type': 'hourly',
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38_half.id,
        })

        sick_leaves = (
            {
                'work_entry_type_code': self.sick_leave_codes[0],
                'date_from': date(2023, 7, 10),
                'date_to': date(2023, 7, 20),
                'half_day_period_from': 'pm',
                'half_day_period_to': 'pm',
            },
            {
                'work_entry_type_code': self.sick_leave_codes[0],
                'date_from': date(2023, 11, 1),
                'date_to': date(2024, 6, 1),
                'half_day_period_from': 'pm',
                'half_day_period_to': 'pm',
            },
            {
                'work_entry_type_code': self.sick_leave_codes[0],
                'date_from': date(2024, 10, 6),
                'date_to': date(2024, 10, 18),
                'half_day_period_from': 'am',
                'half_day_period_to': 'am',
            },
            {
                'work_entry_type_code': self.sick_leave_codes[1],
                'date_from': date(2024, 10, 21),
                'date_to': date(2024, 10, 26),
            },
        )
        compelling_reasons = (
            {
                'work_entry_type_code': self.compelling_reason_codes[0],
                'date_from': date(2023, 8, 20),
                'date_to': date(2023, 8, 25),
            },
            {
                'work_entry_type_code': self.compelling_reason_codes[0],
                'date_from': date(2025, 6, 2),
                'date_to': date(2025, 6, 25),
            },
            {
                'work_entry_type_code': self.compelling_reason_codes[1],
                'date_from': date(2025, 7, 10),
                'date_to': date(2025, 7, 20),
            },
        )
        maternity_leaves = (
            {
                'work_entry_type_code': self.maternity_leave_codes[0],
                'date_from': date(2024, 7, 2),
                'date_to': date(2024, 7, 8),
            },
            {
                'work_entry_type_code': self.maternity_leave_codes[0],
                'date_from': date(2024, 12, 1),
                'date_to': date(2025, 5, 31),
                'half_day_period_from': 'pm',
                'half_day_period_to': 'am',
            },
        )
        unpaid_leaves = (
            {
                'work_entry_type_code': 'test_unpaid',
                'date_from': date(2024, 9, 4),
                'date_to': date(2024, 9, 4),
                'half_day_period_from': 'pm',
                'half_day_period_to': 'pm',
            },
        )
        paid_leaves = (
            {
                'work_entry_type_code': '016.00',  # paid legal leave
                'date_from': date(2024, 10, 2),
                'date_to': date(2024, 10, 4),
            },
        )

        for leave in (
            *sick_leaves,
            *compelling_reasons,
            *maternity_leaves,
            *unpaid_leaves,
            *paid_leaves,
        ):
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=leave['work_entry_type_code'],
                date_from=leave['date_from'],
                date_to=leave['date_to'],
                half_day_period_from=leave.get('half_day_period_from'),
                half_day_period_to=leave.get('half_day_period_to'),
            )

        def part_time_work_hours_in_period(date_from, date_to, half_day_from=None, half_day_to=None) -> float:
            days_in_period = self._get_week_day_count_in_period(date_from, date_to)
            mondays = days_in_period.get('monday', 0)
            tuesdays = days_in_period.get('tuesday', 0)
            wednesdays = days_in_period.get('wednesday', 0)
            hours_in_period = (mondays + tuesdays) * 7.6 + wednesdays * 4
            if half_day_from == 'pm' and date_from.weekday() in [0, 1, 2]:
                # remove morning work hours from start day
                hours_in_period -= 4
            if half_day_to == 'am' and date_from.weekday() in [0, 1]:
                # remove afternoon work hours from end day
                hours_in_period -= 3.6
            return hours_in_period

        def cap_period(date_from, date_to, half_day_from, half_day_to, cap_min, cap_max):
            """
            Caps a given leave period to th cap_min and cap_max dates. Returns
            None if given period is out of cap.
            """
            if date_to < cap_min or date_from > cap_max:
                return None
            if date_from < cap_min:
                date_from = cap_min
                half_day_from = None
            if date_to > cap_max:
                date_to = cap_max
                half_day_to = None
            return date_from, date_to, half_day_from, half_day_to

        # hours before contract are not worked, so not asssimilated
        unassimilated_hours = part_time_work_hours_in_period(date(2023, 1, 1), employee.contract_date_start)

        sick_leave_hours = 0
        for sick_leave in sick_leaves:
            capped_period = cap_period(
                sick_leave['date_from'],
                sick_leave['date_to'],
                sick_leave.get('half_day_period_from'),
                sick_leave.get('half_day_period_to'),
                date(2023, 6, 15),
                date(2023, 12, 31),
            )
            if not capped_period:
                continue
            sick_leave_hours += part_time_work_hours_in_period(*capped_period)

        # no uninterrupted sick leave period is >= 6 months
        unassimilated_hours += sick_leave_hours

        # all compelling reasons will be assimilated for 2023 (< 10 days)

        max_13th_month = employee.hourly_wage * employee.version_id.resource_calendar_id.hours_per_week * (4 + 1 / 3)
        work_hours_2023 = part_time_work_hours_in_period(date(2023, 1, 1), date(2023, 12, 31))
        wanted_amount = round(max_13th_month * (work_hours_2023 - unassimilated_hours) / work_hours_2023, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2023, 12, 1),
            "date_to": date(2023, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A part time employee whose contract started mid-year with multiple leave types
in the year did not get the expected value for its 13th month in december of
2023
        """)

        unassimilated_hours = 0

        sick_leave_hours = 0
        for sick_leave in sick_leaves:
            capped_period = cap_period(
                sick_leave['date_from'],
                sick_leave['date_to'],
                sick_leave.get('half_day_period_from'),
                sick_leave.get('half_day_period_to'),
                date(2024, 1, 1),
                date(2024, 12, 31),
            )
            if not capped_period:
                continue
            sick_leave_hours += part_time_work_hours_in_period(*capped_period)

        # this variable is an average. Here is should be (7.6 * 2 + 4) / 3
        hours_per_day = employee.version_id.resource_calendar_id.hours_per_day

        # the long sick leave period is assimilated at 50%
        assimilated_sick_leave_hours = part_time_work_hours_in_period(date(2024, 1, 1), date(2024, 5, 31)) * 0.5
        unassimilated_hours += sick_leave_hours - assimilated_sick_leave_hours

        # maternity leaves are all assimilated in 2024

        for unpaid_leave in unpaid_leaves:
            capped_period = cap_period(
                unpaid_leave['date_from'],
                unpaid_leave['date_to'],
                unpaid_leave.get('half_day_period_from'),
                unpaid_leave.get('half_day_period_to'),
                date(2024, 1, 1),
                date(2024, 12, 31),
            )
            if not capped_period:
                continue
            unassimilated_hours += part_time_work_hours_in_period(*capped_period)

        work_hours_2024 = part_time_work_hours_in_period(date(2024, 1, 1), date(2024, 12, 31))
        wanted_amount = round(max_13th_month * (work_hours_2024 - unassimilated_hours) / work_hours_2024, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A part time employee whose contract started more than year ago with multiple
leave types in the year did not get the expected value for its 13th month in
december of 2024
        """)

        unassimilated_hours = 0

        compelling_reason_hours = 0
        for compelling_reason in compelling_reasons:
            capped_period = cap_period(
                compelling_reason['date_from'],
                compelling_reason['date_to'],
                compelling_reason.get('half_day_period_from'),
                compelling_reason.get('half_day_period_to'),
                date(2025, 1, 1),
                date(2025, 12, 31),
            )
            if not capped_period:
                continue
            compelling_reason_hours += part_time_work_hours_in_period(*capped_period)

        # max 10 days of compelling reasons can be assimilated
        unassimilated_hours += compelling_reason_hours - 10 * hours_per_day

        maternity_leave_hours = 0
        for maternity_leave in maternity_leaves:
            capped_period = cap_period(
                maternity_leave['date_from'],
                maternity_leave['date_to'],
                maternity_leave.get('half_day_period_from'),
                maternity_leave.get('half_day_period_to'),
                date(2025, 1, 1),
                date(2025, 12, 31),
            )
            if not capped_period:
                continue
            maternity_leave_hours += part_time_work_hours_in_period(*capped_period)

        # the maternity leave cannot be longer than 15 weeks, then only the days
        # below that limit can be assimilated in 2025
        assimilated_maternity_hours = part_time_work_hours_in_period(
            date(2025, 1, 1), date(2024, 12, 1) + timedelta(days=7 * 15 - 1),
        )
        unassimilated_hours += maternity_leave_hours - assimilated_maternity_hours

        work_hours_2025 = part_time_work_hours_in_period(date(2025, 1, 1), date(2025, 12, 31))
        wanted_amount = round(max_13th_month * (work_hours_2025 - unassimilated_hours) / work_hours_2025, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A part time employee whose contract started more than year ago with multiple
leave types in the year did not get the expected value for its 13th month in
december of 2025
        """)

        employee.departure_date = date(2025, 8, 1)
        # we can reuse the unassimilated hours as all the leaves are still
        # before the contract date end
        unassimilated_hours += part_time_work_hours_in_period(date(2025, 8, 2), date(2025, 12, 31))
        wanted_amount = round(max_13th_month * (work_hours_2025 - unassimilated_hours) / work_hours_2025, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 8, 1),
            "date_to": date(2025, 8, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A part time employee whose contract ends sooner than the end of year, with many
different leaves did not get the expected value for its 13th month in 2025
        """)

        employee.departure_reason_id = self.env.ref('hr.departure_retired')
        employee.departure_date = False
        employee.departure_date = date(2025, 8, 1)
        assimilable_retirement_hours = part_time_work_hours_in_period(date(2025, 8, 1), date(2025, 12, 31))
        unassimilated_hours -= assimilable_retirement_hours
        wanted_amount = round(max_13th_month * (work_hours_2025 - unassimilated_hours) / work_hours_2025, 2)
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 8, 1),
            "date_to": date(2025, 8, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        amount = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, wanted_amount, msg="""
A part time employee whose contract retires sooner than the end of year, with
many different leaves should still have all his days assimilated up until the
end of year
        """)

    def test_get_uninterrupted_leave_of_category(self):
        """
        payslip._l10n_be_get_uninterrupted_leave_of_category() should return the
        period boundaries of the consecutive leave of a given category around
        the given datetime.
        This test will also test the derivateive function
        _get_uninterrupted_leaves_of_category_in_range()
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2022, 1, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
        })

        self.env['hr.work.entry.type'].create({
            'name': 'Work entry working time allow on top',
            'count_as': 'working_time',
            'allow_request_on_top': True,
            'code': 'work_test',
            'requires_allocation': False,
            'request_unit': 'half_day',
            'country_id': self.env.ref('base.be').id,
        })

        # these should not effect anything as they are still work time
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code="work_test",
            date_from=date(2025, 2, 2),
            date_to=date(2025, 2, 10),
            half_day_period_from='am',
            half_day_period_to='pm',
        )
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code="work_test",
            date_from=date(2025, 2, 15),
            date_to=date(2025, 2, 18),
            half_day_period_from='am',
            half_day_period_to='pm',
        )
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code="work_test",
            date_from=date(2025, 2, 20),
            date_to=date(2025, 2, 25),
            half_day_period_from='am',
            half_day_period_to='pm',
        )
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code="work_test",
            date_from=date(2025, 4, 9),
            date_to=date(2025, 4, 10),
            half_day_period_from='am',
            half_day_period_to='pm',
        )

        leaves = [
            # those three leaves are consecutive (just separated by weekend)
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[0],
                date_from=date(2025, 2, 4),  # tuesday
                date_to=date(2025, 2, 7),  # friday
                half_day_period_from='am',
                half_day_period_to='pm',
            ),
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[1],
                date_from=date(2025, 2, 10),  # monday
                date_to=date(2025, 2, 14),  # friday
                half_day_period_from='am',
                half_day_period_to='pm',
            ),
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[1],
                date_from=date(2025, 2, 17),  # monday
                date_to=date(2025, 2, 18),  # tuesday
                half_day_period_from='am',
                half_day_period_to='pm',
            ),

            # those two leaves are sperated by half a day
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[0],
                date_from=date(2025, 3, 10),  # monday
                date_to=date(2025, 3, 12),  # wednesday
                half_day_period_from='am',
                half_day_period_to='am',
            ),
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[0],
                date_from=date(2025, 3, 13),  # thursday
                date_to=date(2025, 3, 14),  # friday
                half_day_period_from='am',
                half_day_period_to='am',
            ),

            # those two leaves are not consecutive (sepataed by other leave)
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[0],
                date_from=date(2025, 4, 3),  # thursday
                date_to=date(2025, 4, 7),  # monday
                half_day_period_from='am',
                half_day_period_to='pm',
            ),
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.maternity_leave_codes[0],
                date_from=date(2025, 4, 8),  # tuesday
                date_to=date(2025, 4, 8),  # tuesday
                half_day_period_from='am',
                half_day_period_to='pm',
            ),
            self._create_leave_from_we_type_code(
                employee=employee,
                work_entry_type_code=self.sick_leave_codes[0],
                date_from=date(2025, 4, 9),  # wednesday
                date_to=date(2025, 4, 10),  # thursday
                half_day_period_from='am',
                half_day_period_to='pm',
            ),
        ]

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2025, 12, 1),
            "date_to": date(2025, 12, 31),
            "struct_id": self.cp200_struct.id,
        })

        one_day = timedelta(days=1)
        one_hour = timedelta(hours=1)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[0].date_from - one_hour)
        self.assertEqual(None, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should return None if the reference date is before any leave
        """)

        for reference_date in (
                leaves[0].date_from, leaves[0].date_to,
                leaves[0].date_to + one_day,  # weekend between the leaves
                leaves[1].date_from, leaves[1].date_to,
                leaves[1].date_to + one_day,  # weekend between the leaves
                leaves[2].date_from, leaves[2].date_to,
        ):
            uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', reference_date)
            expected_range = {'start': leaves[0].date_from, 'stop': leaves[2].date_to}
            self.assertEqual(expected_range, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should return all consecutive leaves
in the same category, even if they are separated by weekends without work.
            """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[2].date_to + one_hour)
        self.assertEqual(None, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should return None if the reference date is not in any uninterrupted leave
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[3].date_from)
        expected_range = {'start': leaves[3].date_from, 'stop': leaves[3].date_to}
        self.assertEqual(expected_range, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should not consider two leaves separated
by half a day one uninterrupted leave
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[3].date_to + one_hour)
        self.assertEqual(None, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should not consider the half a day
period between two leaves as part of one whole uninterrupted leave
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[4].date_from)
        expected_range = {'start': leaves[4].date_from, 'stop': leaves[4].date_to}
        self.assertEqual(expected_range, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should not consider two leaves separated
by half a day one uninterrupted leave
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[5].date_from)
        expected_range = {'start': leaves[5].date_from, 'stop': leaves[5].date_to}
        self.assertEqual(expected_range, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should not consider two leaves separated
by a leave of another category as one uninterrupted period
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[6].date_from)
        self.assertEqual(None, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should return None if the leave on
the reference date is of another category than the specified one
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[7].date_from)
        expected_range = {'start': leaves[7].date_from, 'stop': leaves[7].date_to}
        self.assertEqual(expected_range, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should not consider two leaves separated
by a leave of another category as one uninterrupted period
        """)

        uninterrupted_range = payslip._l10n_be_get_uninterrupted_leave_of_category('sick_leave', leaves[-1].date_to + one_day)
        self.assertEqual(None, uninterrupted_range, """
_l10n_be_get_uninterrupted_leave_of_category() should return None if the reference date is after any leave
        """)

        uninterrupted_ranges = payslip._l10n_be_get_uninterrupted_leaves_of_category_in_range(
            'sick_leave',
            leaves[0].date_from + one_day,
            leaves[1].date_to + one_day,
        )
        expected_ranges = [{
                'start': leaves[0].date_from,
                'stop': leaves[2].date_to,
            }]
        self.assertEqual(uninterrupted_ranges, expected_ranges, '''
_l10n_be_get_uninterrupted_leaves_of_category_in_range() should return the non-capped
uninterrupted ranges that go over the given period.
        ''')

        uninterrupted_ranges = payslip._l10n_be_get_uninterrupted_leaves_of_category_in_range(
            'sick_leave',
            datetime.combine(date(2025, 1, 1), time.min),
            datetime.combine(date(2025, 12, 31), time.max),
        )
        expected_ranges = [
            {
                'start': leaves[0].date_from,
                'stop': leaves[2].date_to,
            },
            {
                'start': leaves[3].date_from,
                'stop': leaves[3].date_to,
            },
            {
                'start': leaves[4].date_from,
                'stop': leaves[4].date_to,
            },
            {
                'start': leaves[5].date_from,
                'stop': leaves[5].date_to,
            },
            {
                'start': leaves[7].date_from,
                'stop': leaves[7].date_to,
            },
        ]
        self.assertEqual(uninterrupted_ranges, expected_ranges, '''
_l10n_be_get_uninterrupted_leaves_of_category_in_range() should return the non-capped
ranges that go over the given period.
        ''')

    def test_payslip_line_13th_month_contribution(self):
        """
        Each month, a social contribution should be send to the horeca fund.
        This value depends on the current month's wage, and may vary from
        employees to workers
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 1, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        payslip.action_validate()
        self.assertEqual(payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEENCONTRIBWORK']]).total, 0, """
CP302THIRTEENCONTRIBWORK should always be empty when the employee is not a worker
        """)
        contribution = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEENCONTRIBEMP']])
        payslip_wage = payslip.line_ids.filtered_domain([['code', '=', 'SALARY']])
        self.assertAlmostEqual(contribution.total, round(payslip_wage.total * 0.12, 2), msg="""
The thirteen month contribution of an employee under the cp302 should be 12% of
the gross salary submitted to the ONSS.
        """)

        # make employee a worker
        employee.l10n_be_worker_code_id = self.env['l10n.be.worker.code'].search([('dmfa_code', '=', '015')])
        employee.hourly_wage = 15
        employee.wage_type = 'hourly'

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        payslip.action_validate()
        self.assertEqual(payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEENCONTRIBEMP']]).total, 0, """
CP302THIRTEENCONTRIBEMP should always be empty when the employee is a worker
        """)
        contribution = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEENCONTRIBWORK']])
        payslip_wage = payslip.line_ids.filtered_domain([['code', '=', 'SALARY']])
        self.assertAlmostEqual(contribution.total, round(payslip_wage.total * 1.08 * 0.12, 2), msg="""
The thirteen month contribution of a worker under the cp302 should be 12% of 108%
of the gross salary submitted to the ONSS.
        """)

    def test_payslip_line_thirteen_month(self):
        """
        All previous tests were calling the function directly. This one will
        test if the payslip line computation does work well.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'hourly',
            'hourly_wage': 10,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip.compute_sheet()
        thirteen_month = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']])
        wanted_amount = round(employee.hourly_wage * employee.version_id.resource_calendar_id.hours_per_week * (4 + 1 / 3), 2)
        self.assertAlmostEqual(thirteen_month.total, wanted_amount, msg="""
The payslip line of the cp302's thirteen month did not return an expected value
        """)

    def test_seniority_gap_day(self):
        """
        The seniority of the employee/worker should be reset if there is a
        working time gap between two of his versions
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
        })
        employee.version_id.contract_date_end = date(2024, 11, 13)  # Wednesday
        employee.create_version({
            'date_version': date(2024, 11, 15),  # Friday
            'contract_date_start': date(2024, 11, 15),
            'wage_type': 'monthly',
            'wage': 4000,
            'resource_calendar_id': self.resource_calendar_38.id,
        })

        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 12, 1),
            "date_to": date(2024, 12, 31),
            "struct_id": self.cp200_struct.id,
        })

        payslip.compute_sheet()
        thirteen_month = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']])
        self.assertAlmostEqual(thirteen_month.total, 0, msg="""
An employee with unconsecutive versions that break his seniority should not receive
his 13th month if his seniority is < 2 months after being broken up
        """)

        employee.create_version({
            'date_version': date(2024, 11, 14),  # Thursday
            'contract_date_start': date(2024, 11, 14),
            'contract_date_end': date(2024, 11, 14),
            'wage_type': 'monthly',
            'wage': 4000,
            'resource_calendar_id': self.resource_calendar_38.id,
        })

        payslip.compute_sheet()
        thirteen_month = payslip.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']])
        self.assertAlmostEqual(thirteen_month.total, employee.wage, msg="""
An employee with only consecutive versions for more than 2 months should receive
his 13th month as no unworked period breaks his seniority
        """)

    def test_partena_long_sick_days_accross_year_combination(self):
        """
        Test given from PARTENA:
        - if there is a sick period of 4 months (01/09/2024 => 31/12/2024), then only 4 months. Nothing is assimilated.
        - if he is sick 3 more months (01/01/2025 => 31/03/2025) total 7 months, 3 months are assimilated at 50% in 2025.
        - then he works from 01/04/2025 => 31/05/2025 (2 months)
        - then he is sick again for 6 months (01/06/2025 => 31/12/2025)
        - then for the whole year of 2025, 6 months are assimilated at 50% (the 3 months in the first period + 3 months in the last period)
        This is because we can assimilate up to 6 months per year from uninterrupted sick leave periods of at least 6 months
        """
        week_days_2024 = sum(self._get_week_day_count_in_period(date(2024, 1, 1), date(2024, 12, 31)).values())
        week_days_2025 = sum(self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 12, 31)).values())
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'monthly',
            'wage': 3000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
        })

        payslip_2024, payslip_2025 = self.env['hr.payslip'].create([
            {
                'name': "Payslip Partena Test 2024",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2024, 12, 1),
                "date_to": date(2024, 12, 31),
                "struct_id": self.cp200_struct.id,
            },
            {
                'name': "Payslip Partena Test 2025",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 12, 1),
                "date_to": date(2025, 12, 31),
                "struct_id": self.cp200_struct.id,
            },
        ])

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2024, 9, 1),
            date_to=date(2024, 12, 31),
        )
        week_days_leave_1 = sum(self._get_week_day_count_in_period(date(2024, 9, 1), date(2024, 12, 31)).values())
        assimilated_days = week_days_2024 - week_days_leave_1
        expected_13th_month = round(employee.wage * (assimilated_days / week_days_2024), 2)
        payslip_2024.compute_sheet()
        thirteen_month = payslip_2024.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(expected_13th_month, thirteen_month, msg="""
        If the employee only has 4 months of uninterrupted sick leaves, then
        nothing of the leave can be assimilated
        """)

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 31),
        )
        week_days_leave_2 = sum(self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 3, 31)).values())
        assimilated_days = week_days_2025 - week_days_leave_2 * 0.5
        expected_13th_month = round(employee.wage * (assimilated_days / week_days_2025), 2)
        payslip_2025.compute_sheet()
        thirteen_month = payslip_2025.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(expected_13th_month, thirteen_month, msg="""
        If the employee only has 3 months of uninterrupted sick leave in the
        current year, but this leave is longer than 6 months if we consider the
        previous year, then the 3 months can be assimilated in the 13th month
        """)

        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.sick_leave_codes[0],
            date_from=date(2025, 6, 1),
            date_to=date(2025, 12, 31),
        )
        week_days_leave_3 = sum(self._get_week_day_count_in_period(date(2025, 6, 1), date(2025, 12, 31)).values())
        assimilable_days_leave_3 = sum(self._get_week_day_count_in_period(date(2025, 6, 1), date(2025, 8, 31)).values())
        assimilated_days = week_days_2025 - week_days_leave_2 * 0.5 - (week_days_leave_3 - assimilable_days_leave_3 * 0.5)
        expected_13th_month = round(employee.wage * (assimilated_days / week_days_2025), 2)
        payslip_2025.compute_sheet()
        thirteen_month = payslip_2025.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(expected_13th_month, thirteen_month, msg="""
        If the employee only has 3 months of uninterrupted sick leave in the
        current year, but this leave is longer than 6 months if we consider the
        previous year, then the 3 months can be assimilated in the 13th month
        AND if the employee also has another period >= 6 uninterrupted months in
        that same year, then it can also be assimilated (but it's capped to 6
        months per year, so only 3 months will be assimilated)
        """)

    def test_multiple_13th_month_same_year(self):
        """
        If an employee gets his 13th months early in the year (e.g.: he leaves),
        then continues working later in the year (e.g.: his departure is cancelled),
        then he will get his 13th month again later in the year. During the second
        computation, the first 13th month should be deduced from the second one.
        """
        self.skipTest('MLEF TODO: Crashing test in 19.5 master to reintroduce')
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
            'wage_type': 'hourly',
            'hourly_wage': 20,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
            'l10n_be_worker_code_id': self.env['l10n.be.worker.code'].search([('dmfa_code', '=', '015')]).id,
        })
        max_13th_month = round(employee.hourly_wage * employee.version_id.resource_calendar_id.hours_per_week * (4 + 1 / 3), 2)

        # generate a payslip the year before to make sure it does not affect the
        # payslip after (this one should not be deducted from the 13th month in 2025)
        payslip_2024 = self.env['hr.payslip'].create(
            {
                'name': "April last year payslip",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2024, 12, 1),
                "date_to": date(2024, 12, 31),
                "struct_id": self.cp200_struct.id,
            },
        )
        payslip_2024.action_validate()
        thirteen_month_2024 = payslip_2024.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(max_13th_month, thirteen_month_2024, msg="""
A basic test for a worker 13th month in december failed (should have been his
weekly salary * 4.333...)
        """)

        departure = self.env['hr.employee.departure'].create([{
            'employee_id': employee.id,
            'dismissal_date': date(2025, 4, 1),
            "l10n_be_notice_respect": "without",
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'departure_description': "Didn't bring coffee",
        }])
        employee.departure_id = departure

        payslip_april = self.env['hr.payslip'].create(
            {
                'name': "April last year payslip",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 4, 1),
                "date_to": date(2025, 4, 30),
                "struct_id": self.cp200_struct.id,
            },
        )
        # entire leave should be assimilated
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.paternity_leave_codes[0],
            date_from=date(2025, 3, 3),  # monday
            date_to=date(2025, 3, 7),  # friday
        )
        week_days_2025 = sum(self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 12, 31)).values())
        assimilated_days = sum(self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 4, 1)).values())
        expected_13th_month = round(max_13th_month * assimilated_days / week_days_2025, 2)
        payslip_april.action_validate()
        thirteen_month_april = payslip_april.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(expected_13th_month, thirteen_month_april, msg="""
An employee whose contract ended on the 1st of April did not receive his 13th
month with the correct proratization.
        """)

        # April fools! You're actually not terminated. ahah.
        employee.departure_id = False

        payslip_december = self.env['hr.payslip'].create(
            {
                'name': "December payslip",
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                "date_from": date(2025, 12, 1),
                "date_to": date(2025, 12, 31),
                "struct_id": self.cp200_struct.id,
            },
        )
        # entire leave should be assimilated (now all 10 days are assimilated)
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.paternity_leave_codes[0],
            date_from=date(2025, 6, 2),  # monday
            date_to=date(2025, 6, 6),  # friday
        )
        # max 10 days of paternity leaves can be assimilated, so this leave isn't
        self._create_leave_from_we_type_code(
            employee=employee,
            work_entry_type_code=self.paternity_leave_codes[0],
            date_from=date(2025, 6, 9),  # monday
            date_to=date(2025, 6, 13),  # friday
        )
        week_days_2025 = sum(self._get_week_day_count_in_period(date(2025, 1, 1), date(2025, 12, 31)).values())
        assimilated_days = week_days_2025 - 5  # 5 unassimilated paternity leave days
        expected_13th_month = round(max_13th_month * assimilated_days / week_days_2025, 2)
        expected_13th_month -= thirteen_month_april  # you should not pay again what you've paid in April
        payslip_december.action_validate()
        thirteen_month_december = payslip_december.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(expected_13th_month, thirteen_month_december, msg="""
If an employee has already paid a 13th month during a year, but then works again
and has another 13th month in the same year, than the amount of the first 13th
month should be deduced from the second one.
        """)

    def test_cp302_13th_month_contract_date_end(self):
        """
        A monthly payslip whose month is during a contract_date_end should have
        a 13th month line in the CP302
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2024, 3, 15),
            'wage_type': 'monthly',
            'wage': 3000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
            'l10n_be_worker_code_id': self.env['l10n.be.worker.code'].search([('dmfa_code', '=', '015')]).id,
        })

        payslip_march = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 3, 1),
            "date_to": date(2024, 3, 31),
            "struct_id": self.cp200_struct.id,
        })
        payslip_march.compute_sheet()
        payslip_march.action_validate()
        thirteen_month_march = payslip_march.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        work_days_2024 = sum(
            self._get_week_day_count_in_period(date(2024, 1, 1), date(2024, 12, 31)).values(),
        )
        worked_days = sum(
            self._get_week_day_count_in_period(date(2024, 1, 1), employee.contract_date_end).values(),
        )
        expected_13th_month = round(employee.wage * (worked_days / work_days_2024), 2)
        self.assertAlmostEqual(expected_13th_month, thirteen_month_march, msg="""
A 13th month should be on a payslip that is during the last day of work of the
year. `contract_date_end` being an indicator of the last work day.
        """)

        employee.create_version({
            'date_version': date(2024, 3, 16),
            'contract_date_start': date(2024, 3, 16),
            'contract_date_end': date(2024, 4, 15),
        })

        payslip_april = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 4, 1),
            "date_to": date(2024, 4, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip_april.compute_sheet()
        payslip_march.action_validate()
        thirteen_month_april = payslip_april.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        worked_days = sum(
            self._get_week_day_count_in_period(date(2024, 1, 1), employee.contract_date_end).values(),
        )

        expected_13th_month = round(employee.wage * (worked_days / work_days_2024), 2)
        # we have to deduce the 13th month already paid in march to not pay it twice
        expected_13th_month -= thirteen_month_march
        self.assertAlmostEqual(expected_13th_month, thirteen_month_april, msg="""
The 13th month should appear on the month if the last work day of the year is
during that month. The last `contract_date_end` of the year defines the date of
the last work day.
        """)

    def test_cp302_ext_allowed_limit(self):
        """
        Temporary workers are a special case. They don't apply to the 2 months
        seniority requirement (because they cannot have that much seniority as
        they can't have more than 2 consecutive work days).
        So, instead, there is a "simple" day limit, that once surpassed, allows
        the "ext" employee to get his 13th month.
        """
        employee = self.env['hr.employee'].create({
            'name': 'Valentino',
            'contract_date_start': date(2023, 1, 1),  # first monday of the year
            'contract_date_end': date(2023, 1, 1),
            'wage': 4000,
            'l10n_be_joint_committee_id': self.cp302.id,
            'resource_calendar_id': self.resource_calendar_38.id,
            'l10n_be_dimona_category': 'ext',
        })

        # 3 days of work per week, so 42 days of work
        work_days = []
        beg_of_year = date(2024, 1, 1)  # also the first monday of the year
        for week in range(0, 14):
            # monday, wednesay and fridays of each week can be worked
            work_days.append(beg_of_year + timedelta(weeks=week))
            work_days.append(beg_of_year + timedelta(weeks=week, days=2))
            work_days.append(beg_of_year + timedelta(weeks=week, days=4))

        for work_day in work_days:
            employee.create_contract(date=work_day)
            employee.contract_date_end = work_day

        # last worked day is in april
        payslip_april = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 4, 1),
            "date_to": date(2024, 4, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip_april.compute_sheet()
        amount = payslip_april.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total
        self.assertAlmostEqual(amount, 0, msg="""
Temporary workers (dimona == 'ext') should not receive their 13th month if they
worked less than 44 days in the year of payment.
        """)

        # work 2 more days, thus making it 44 days of work
        for work_day in (
                beg_of_year + timedelta(weeks=14),
                beg_of_year + timedelta(weeks=14, days=2),
        ):
            employee.create_contract(date=work_day)
            employee.contract_date_end = work_day

        # employee reached the limit of worked days for "ext" dimona. So now
        # he can get his 13th month

        # we need to create another payslip so that it's based off the new version
        payslip_april = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            "date_from": date(2024, 4, 1),
            "date_to": date(2024, 4, 30),
            "struct_id": self.cp200_struct.id,
        })
        payslip_april.compute_sheet()
        amount = payslip_april.line_ids.filtered_domain([['code', '=', 'CP302THIRTEEN']]).total

        # max 13th month * proratized 13th month (worked days / max workable days)
        work_days_2024 = sum(self._get_week_day_count_in_period(
            date(2024, 1, 1), date(2024, 12, 31),
        ).values())
        expected_13th_month = round(employee.wage * 44 / work_days_2024, 2)
        self.assertAlmostEqual(amount, expected_13th_month, msg="""
Temporary workers (dimona == 'ext') should receive their proratized 13th month
if they worked at least 44 days in the year regardless of the seniority limit
        """)
