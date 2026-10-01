# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'alloc_paid_time_off')
class TestPayrollAllocatingPaidTimeOff(TestPayrollCommon):

    def setUp(self):
        super().setUp()

        self.resource_calendar_40_hours = self.resource_calendar.copy({
            'name': 'Test Calendar 40 Hours',
            'hours_per_day': 8,
            'hours_per_week': 40,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17}),
            ],
        })

        self.resource_calendar_6_day_week = self.resource_calendar.copy({
            'name': 'Test Calendar 6 Day Week',
            'hours_per_day': 7.6,
            'hours_per_week': 45.6,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '5', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '5', 'hour_from': 13, 'hour_to': 16.6}),
            ],
        })

        self.resource_calendar_two_weeks = self.resource_calendar.copy({
            'name': 'Two Week Calendar',
            'full_time_required_hours': 38,
            'calendar_type': 'variable',
            'hours_per_day': 7.6,
            'days_per_week': 4.5,
            'hours_per_week': 7.6 * 4.5,
            'attendance_ids': [(0, 0, {
                'date': date(1, 1, 1) + timedelta(days=d, weeks=w),
                'hour_from': 8,
                'hour_to': 15.6,
                'recurrency': True,
                'recurrency_interval': 2,
                'recurrency_type': 'weeks',
                'recurrency_end_type': 'forever',
            }) for d in range(5) for w in range(2) if not (d == 0 and w == 1)],
        })

        with freeze_time('2023-01-01'):

            today = date.today()

            self.employee_gustavo = self.create_employee({
                'name': 'Gustavo Garcia',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'resource_calendar_id': self.resource_calendar_40_hours.id,
                'l10n_be_worker_code_id': self.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            self.employee_fernando = self.create_employee({
                'name': 'Fernando Alonso',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'resource_calendar_id': self.resource_calendar_6_day_week.id,
                'l10n_be_worker_code_id': self.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            self.employee_bertrand = self.create_employee({
                'name': 'Bertrand Guru',
                'date_version': date(today.year - 2, 1, 1),
                'contract_date_start': date(today.year - 2, 1, 1),
                'resource_calendar_id': self.resource_calendar_two_weeks.id,
                'l10n_be_worker_code_id': self.worker_code_id.id,
                'l10n_be_dimona_category': 'oth',
            })

            self.wizard = self.env['hr.payroll.alloc.paid.leave'].create({
                'year': today.year - 1,
            })
            self.wizard.alloc_employee_ids = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id in [self.employee_georges.id, self.employee_john.id, self.employee_with_attestation.id, self.employee_gustavo.id, self.employee_fernando.id, self.employee_bertrand.id])

    def test_allocating_paid_time_off(self):
        """
        Last year, the employee Georges had these contracts:
        - From 01/01 to 31/05, he worked at mid time, 3 days/week
        - From 01/06 to 31/08, he worked at full time, 5 days/week
        - From 01/09 to 31/12, he worked at 4/5, 4 days/week

        and the employee John Doe had these contracts :
        - From 01/01 to 31/03, he worked at full time
        - From 01/04 to 30/06, he worked at 9/10 time
        - From 01/07 to 30/09, he worked at 4/5 time
        - From 01/10 to 31/12, he worked at mid time

        Normally, we must allocate max 14.5 days to Georges and 12 days to John for this year.

        Description of the calculations:
        ------------------------------
        - Georges :
            - From 01/01 to 31/05, he worked at mid time, 3 days/week. We compute this: 152 * 1 / 2 * 5 / 12 = 31.6667 hours
            - From 01/06 to 31/08, he worked at full time, 5 days/week. We compute this: 152 * 3 / 12 = 38 hours
            - From 01/09 to 31/12, he worked at 4/5, 4 days/weeks. We compute this: 152 * 4 / 5 * 4 / 12 = 40.53333 hours
            In total, we have 110,200033333 hours and we convert it in days to have the value in paid_time_off
            which is equal to: 14,500004386 days (rounded DOWN to the nearest half-day: 14.5 days)
            = 110,200033333 / (38 / 5) = 110,200033333 hours / 7.6 hours/day
            (his next year contract is still the 4/5 one, 30.4h/week over 4 days = 7.6 hours/day: same rate as the
            reference calendar here, so it makes no difference which one is used)

        - John Doe :
            - From 01/01 To 03/31, we compute: 152 x 3 / 12 = 38 hours
            - From 04/01 To 06/30, we compute: 152 x 9 / 10 x 3 / 12 = 34.2 hours
            - From 07/01 To 09/30, we compute: 152 x 4 / 5 x 3 / 12 = 30.4 hours
            - From 10/01 To 12/31, we compute: 152 x 1 / 2 x 3 / 12 = 19 hours
            In total, we have 121.6 hours and we convert it in days to have the value in paid_time_off, using his
            *next* year contract's own rate (mid-time, 19h/week over 3 days = 6.3333 hours/day): 121.6 / (19 / 3)
            = 19.2 days, rounded DOWN to 19.0 -- then capped at 4 weeks of his working schedule
            (4 x 3 days/week = 12 days.
        """
        self.assertEqual(len(self.wizard.alloc_employee_ids), 6, "Normally we should find 6 employees to allocate their paid time off for the next period")

        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_georges.id).paid_time_off, 14.5, "Georges should have 14.5 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_john.id).paid_time_off, 12, "John Doe should have 12 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_gustavo.id).paid_time_off, 20, "Gustavo should have 20 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_fernando.id).paid_time_off, 24, "Fernando should have 24 days paid time offs for this year.")
        self.assertEqual(self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_bertrand.id).paid_time_off, 18, "Bertrand should have 18 days paid time offs for this year.")

    def test_reallocate_paid_time_off_based_contract_next_year(self):
        """
        In two first leave we see the paid time off allocated for both employee based on their contract in the last year.
        But we need to check the contract for this year to allocate the correct amount of paid time off.

        This year, Georges begins to work a 4/5 and John continues his last contract at mid-time.

        Description of the calculations:
        ------------------------------
        After the calculation done in test above, we need to cap each of Georges' periods at his new 4/5 rate
        (30.4 hours per week) individually before summing: his full-time period (38 hours/week) is capped down
        to 30.4 hours/week, giving 31.67 + 30.4 + 40.53 = 102.6 hours instead of 110,200033333. We convert this
        in days for Georges, that is :
        102.6 / (30.4 hours per week / 4 days) = 13.5 days

        After the calculation done in test above, we need to convert 121.6 in days for the mid time of John, that is :
        121.6 / (19 hours per week / 3 days) = 19.2 days (we round to 19 days)
        But since an employee should never have more than 4 weeks of paid time off, his total is reduced to 4 weeks of 3 days a week aka 12 days
        """
        self.assertEqual(len(self.wizard.alloc_employee_ids), 6, "Normally, we should find 6 employees to allocate their paid time off for the next period")

        alloc_employee = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_georges.id)
        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 13.5, "With a 4/5 time in this period, Georges could have 16 days of paid time off but his working schedule in last period allow him 13.5 days")
        self.assertAlmostEqual(alloc_employee.hours_to_allocate, 102.8, places=1)

        alloc_employee = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_john.id)
        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 12, "With a mid-time in this period, John Doe should have 12 days of paid time off but we must retain that he could have 16 days at total this period")
        self.assertEqual(alloc_employee.hours_to_allocate, 76)

        view = self.wizard.generate_allocation()
        allocations = self.env['hr.leave.allocation'].search(view['domain'])
        georges_allocation = allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_georges.id)

        self.assertEqual(georges_allocation.number_of_days, 13.5)
        self.assertAlmostEqual(georges_allocation.number_of_hours, 102.8, places=1, msg="based on the last year, we retain that Georges can have at most 16 days of paid time off")

        john_allocation = allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_john.id)

        self.assertEqual(john_allocation.number_of_days, 12)
        self.assertEqual(john_allocation.number_of_hours, 76, "4 weeks * 19h/week, his mid-time schedule's rate")

    def test_allocating_paid_time_off_with_attestation_days(self):
        """
        Last year, the Employee With Attestation had these contracts:
        - He worked 3 months for the previous employer with 50% occupation rate.
        - From 01/10 to 31/12, he worked at full time, 5 days/week

        Normally, we must allocate max 7.5 days to the employee for this year

        Description of the calculations:
        ------------------------------
        - Employee With Attestation :
            - He worked 3 months for the previous employer with 50% occupation rate.
              We compute this: 152 * (3/12) * (50/100) = 19 hours
            - From 01/10 to 31/12, he worked at full time, 5 days/week. We compute this: 152 * 3 / 12 = 38 hours

            In total, we have 57 hours and we convert it in days to have the value in paid_time_off
            which is equal to: 7.5 days (57 hours / 7.6 hours/day, already an exact half-day, so
            rounding DOWN to the nearest half-day leaves it unchanged)
        """
        self.assertEqual(
            self.wizard.alloc_employee_ids.filtered(
                lambda alloc: alloc.employee_id == self.employee_with_attestation
            ).paid_time_off,
            7.5,
            "The employee should have 7.5 days paid time offs for this year.")

    def test_allocating_paid_time_off_with_attestation_shorter_previous_week(self):
        """
        Same situation as above, except the previous employer's own standard week (35h) was
        *shorter* than the current one (38h), both over 5 days/week.

        The attestation period must be capped at the previous employer's own absolute rate (35h),
        not at a percentage of the *current* employer's reference: someone moving from
        a shorter week to a longer one keeps "4 weeks at the old, lower rate", not 4 weeks at the new
        one -- otherwise a previous employer with a shorter week would inflate the entitlement.

        Description of the calculations:
        ------------------------------
        - He worked 3 months for the previous employer, full-time there (35h/week, 5 days/week).
          Capped at min(35, 38) = 35h: ~64/260 of a year * 20 / 5 = ~0.985 weeks * 35h/week = ~34.5h
        - From 01/10 to 31/12, he worked full-time for the current employer (38h/week, 5 days/week):
          ~79/313 of the year * 4 weeks * 38h/week = ~38.4h

        Total ~72.8h, converted to days at the current employer's rate (38h/5 days = 7.6h/day):
        ~72.8 / 7.6 = ~9.58, rounded down to the nearest half-day = 9.5 days.
        """
        year = self.employee_with_attestation.first_contract_date.year

        employee = self.create_employee({
            'name': 'Shorter Previous Week',
            'date_version': date(year, 10, 1),
            'contract_date_start': date(year, 10, 1),
            'contract_date_end': False,
            'resource_calendar_id': self.resource_calendar.id,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
        })
        employee.l10n_be_holiday_attest_ids = [
            Command.create({
                "date_from": date(year, 1, 1),
                "date_to": date(year, 3, 31),
                "prev_work_hours_per_week": 35,
                "prev_reference_work_hours_per_week": 35,
                "prev_work_days_per_week": 5,
                "prev_simple_holiday_pay_paid": 0,
                "prev_double_holiday_pay_paid": 0,
            }),
        ]

        wizard = self.env['hr.payroll.alloc.paid.leave'].create({'year': str(year)})
        alloc_employee = wizard.alloc_employee_ids.filtered(lambda a: a.employee_id == employee)

        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 9.5)
        self.assertAlmostEqual(alloc_employee.hours_to_allocate, 72.83, places=2)

    # This situation occurred during the migration to the version model. Some employees had one version in BE
    # while the rest of their versions were in HK. Normally, this should not happen because we create a separate
    # employee record for each company, and an employee's versions are linked to the company of that employee.
    def test_allocating_paid_time_off_with_versions_in_different_companies(self):
        """
        Last year, the employee Georges had these contracts: :
        - From 01/01 to 31/05, he worked at mid time, 3 days/week   ->   BE Company
        - From 01/06 to 31/08, he worked at full time, 5 days/week  ->   BE Company
        - From 01/09 to 31/12, he worked at 4/5, 4 days/week        ->   HK Company

        Since Georges switched to HK company on 01/09, there shouldn't be any allocation for him.
        """
        with freeze_time('2023-12-01'):
            hongkong_company = self.env['res.company'].create({
                'name': 'My HK Company - Test',
                'country_id': self.env.ref('base.hk').id,
                'currency_id': self.env.ref('base.EUR').id,
                'street': 'not Rue du Paradis',
                'zip': '6870',
                'city': 'not Eghezee',
                'vat': 'BE0897223670',
                'phone': '061928374',
            })
            self.employee_georges.company_id = hongkong_company.id
            self.employee_georges.flush_recordset()
            last_year = date.today().year - 1
            target_dates = [
                date(last_year, 1, 1),
                date(last_year, 6, 1),
            ]
            versions = self.employee_georges.version_ids.search([
                ('date_version', 'in', target_dates)
            ])
            versions.write({'company_id': self.belgian_company.id})
            self.wizard = self.env['hr.payroll.alloc.paid.leave'].create({
                'year': date.today().year - 1,
            })
            self.wizard.alloc_employee_ids = self.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_georges.id)
            self.assertEqual(len(self.wizard.alloc_employee_ids), 0, "Since Georges switched to HK company on 01/09, there shouldn't be any allocation for him.")

    def test_create_allocation_holiday_attest(self):
        work_entry_type = self.env.ref("hr_work_entry.be_work_entry_type_legal_leave")
        ALLOCATION_DAYS = 10
        self.employee_georges.l10n_be_holiday_attest_ids = [
            Command.create({
                "date_from": date(self.employee_georges.first_contract_date.year - 1, 1, 1),
                "date_to": date(self.employee_georges.first_contract_date.year - 1, 12, 31),
                "prev_work_time_rate": 1,
                "prev_work_days_per_week": 5,
                "prev_days_earned": ALLOCATION_DAYS,
                "prev_simple_holiday_pay_paid": 1000,
                "prev_double_holiday_pay_paid": 0,
            }),
        ]
        allocation = self.employee_georges.l10n_be_holiday_attest_ids.leave_allocation_id

        self.assertTrue(allocation)
        self.assertEqual(allocation.number_of_days, ALLOCATION_DAYS)
        self.assertEqual(allocation.state, "confirm")
        self.assertTrue(allocation.work_entry_type_id.id in work_entry_type.ids)
        self.assertEqual(allocation.date_from, date(self.employee_georges.first_contract_date.year, 1, 1))
        self.assertEqual(allocation.date_to, date(self.employee_georges.first_contract_date.year, 12, 31))

    def test_allocating_paid_time_off_employee_with_flexible_calendar(self):
        """
        Verify that computing allocated paid time off does not crash
        for an employee whose working schedule is a flexible calendar with
        no predefined slots but an hours target (Belgian employees must have
        one: hr.version._check_hours_per_week_required).
        """
        today = date.today()
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'company_id': self.belgian_company.id,
            'calendar_type': 'undefined',
            'hours_per_week': 38,
            'hours_per_day': 7.6,
        })
        employee_flexible = self.create_employee({
            'name': 'Flexible Employee',
            'date_version': date(today.year - 2, 1, 1),
            'contract_date_start': date(today.year - 2, 1, 1),
            'resource_calendar_id': flexible_calendar.id,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
        })

        wizard = self.env['hr.payroll.alloc.paid.leave'].create({
            'year': today.year - 1,
        })

        alloc_line = wizard.alloc_employee_ids.filtered(
            lambda alloc: alloc.employee_id == employee_flexible
        )

        self.assertEqual(alloc_line.paid_time_off, 0)

    def test_create_allocation_public_holiday_non_working_day(self):
        public_holiday = self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday on Weekend',
            'date_from': datetime(2023, 1, 8, 0, 0, 0),
            'date_to': datetime(2023, 1, 8, 23, 59, 59),
            'company_id': self.belgian_company.id,
        })

        action = public_holiday.action_open_multi_allocations_wizard()
        self.assertIsInstance(action, dict, "action_open_multi_allocations_wizard() should return a wizard action for non-working day public holidays.")
        self.assertEqual(action['res_model'], 'hr.leave.allocation.generate.multi.wizard')

        wizard = self.env['hr.leave.allocation.generate.multi.wizard'].with_context(**action['context']).create({})
        wizard.employee_ids = self.employee_georges
        wizard.action_generate_allocations()

        allocations = self.env['hr.leave.allocation'].search([
            ('public_holiday_id', '=', public_holiday.id),
        ])

        self.assertEqual(len(allocations), 1, "Employee Georges should have received one Public Holiday Compensation allocation.")
        self.assertEqual(allocations.number_of_days, 1.0, "The Public Holiday Compensation allocation should be for 1 day.")
        self.assertEqual(allocations.state, 'validate', "The Public Holiday Compensation allocation should be approved.")
        self.assertEqual(allocations.date_from, public_holiday.date_to.replace(day=1).date(), "The allocation's date_from should be the first day of the month of the public holiday.")
        self.assertEqual(allocations.date_to, public_holiday.date_to.replace(day=31, month=12).date(), "The allocation's date_to should be the last day of the year of the public holiday.")

    def test_create_allocation_public_holiday_non_working_day_new_employee(self):
        public_holiday = self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday on Weekend',
            'date_from': datetime(2023, 1, 1, 0, 0, 0),
            'date_to': datetime(2023, 1, 1, 23, 59, 59),
            'company_id': self.belgian_company.id,
        })

        action = public_holiday.action_open_multi_allocations_wizard()
        self.assertIsInstance(action, dict, "action_open_multi_allocations_wizard() should return a wizard action.")

        new_employee = self.create_employee({
            'name': 'New Employee',
            'date_version': date(2023, 1, 1),
            'contract_date_start': date(2023, 1, 1),
            'resource_calendar_id': self.resource_calendar_40_hours.id,
        })

        wizard = self.env['hr.leave.allocation.generate.multi.wizard'].with_context(**action['context']).create({})
        wizard.employee_ids = new_employee
        wizard.action_generate_allocations()

        allocations = self.env['hr.leave.allocation'].search([
            ('public_holiday_id', '=', public_holiday.id),
        ])
        self.assertEqual(len(allocations), 1, "The new employee should have received one Public Holiday Compensation allocation.")
        self.assertEqual(allocations.number_of_days, 1.0, "The Public Holiday Compensation allocation should be for 1 day.")
        self.assertEqual(allocations.state, 'validate', "The Public Holiday Compensation allocation should be approved.")
        self.assertEqual(allocations.date_from, public_holiday.date_to.replace(day=1).date(), "The allocation's date_from should be the first day of the month of the public holiday.")
        self.assertEqual(allocations.date_to, public_holiday.date_to.replace(day=31, month=12).date(), "The allocation's date_to should be the last day of the year of the public holiday.")

    def test_linkable_allocation_ids_only_matches_correct(self):
        """
        Only an allocation matching the employee, the holiday year and the legal-leave
        work entry type for the employee type is offered as a linkable candidate.
        """
        legal_leave = self.env.ref("hr_work_entry.be_work_entry_type_legal_leave")
        worker_time_off = self.env.ref("hr_work_entry.l10n_be_work_entry_type_worker_time_off")
        holiday_year = self.employee_georges.first_contract_date.year

        correct_allocation, _wrong_year, _wrong_time_type, _wrong_employee = self.env["hr.leave.allocation"].create([
            {
                "name": "Correct",
                "employee_id": self.employee_georges.id,
                "work_entry_type_id": legal_leave.id,
                "number_of_days": 20,
                "date_from": date(holiday_year, 1, 1),
                "date_to": date(holiday_year, 12, 31),
                "state": "confirm",
            },
            # Wrong year: right employee and work entry type, but the year before the holiday year.
            {
                "name": "Wrong year",
                "employee_id": self.employee_georges.id,
                "work_entry_type_id": legal_leave.id,
                "number_of_days": 20,
                "date_from": date(holiday_year - 1, 1, 1),
                "date_to": date(holiday_year - 1, 12, 31),
                "state": "confirm",
            },
            # Wrong work entry type: right employee and year, but not the legal-leave type.
            {
                "name": "Wrong work entry type",
                "employee_id": self.employee_georges.id,
                "work_entry_type_id": worker_time_off.id,
                "number_of_days": 20,
                "date_from": date(holiday_year, 1, 1),
                "date_to": date(holiday_year, 12, 31),
                "state": "confirm",
            },
            # Wrong employee: right work entry type and year, but a different employee.
            {
                "name": "Wrong employee",
                "employee_id": self.employee_john.id,
                "work_entry_type_id": legal_leave.id,
                "number_of_days": 20,
                "date_from": date(holiday_year, 1, 1),
                "date_to": date(holiday_year, 12, 31),
                "state": "confirm",
            },
        ])

        attestation = self.env["l10n.be.holiday.attest"].create({
            "employee_id": self.employee_georges.id,
            "date_from": date(holiday_year - 1, 1, 1),
            "date_to": date(holiday_year - 1, 12, 31),
            "prev_work_time_rate": 1,
            "prev_work_days_per_week": 5,
            "prev_days_earned": 10,
            "prev_simple_holiday_pay_paid": 1000,
            "prev_double_holiday_pay_paid": 0,
        })

        self.assertEqual(attestation.linkable_allocation_ids, correct_allocation)

    def test_linkable_allocation_ids_excludes_refused(self):
        """A refused allocation must not be offered as a candidate."""
        legal_leave = self.env.ref("hr_work_entry.be_work_entry_type_legal_leave")
        holiday_year = self.employee_georges.first_contract_date.year

        refused_allocation = self.env["hr.leave.allocation"].create({
            "name": "Refused",
            "employee_id": self.employee_georges.id,
            "work_entry_type_id": legal_leave.id,
            "number_of_days": 20,
            "date_from": date(holiday_year, 1, 1),
            "date_to": date(holiday_year, 12, 31),
            "state": "confirm",
        })
        refused_allocation.action_refuse()

        attestation = self.env["l10n.be.holiday.attest"].new({
            "employee_id": self.employee_georges.id,
            "date_from": date(holiday_year - 1, 1, 1),
            "date_to": date(holiday_year - 1, 12, 31),
            "prev_work_time_rate": 1,
            "prev_work_days_per_week": 5,
            "prev_days_earned": 10,
            "prev_simple_holiday_pay_paid": 1000,
            "prev_double_holiday_pay_paid": 0,
        })

        self.assertFalse(attestation.linkable_allocation_ids)

    def test_linkable_allocation_ids_worker_employee_type(self):
        """For a Worker the candidate work entry type is the worker time off type, not legal leave."""
        legal_leave = self.env.ref("hr_work_entry.be_work_entry_type_legal_leave")
        worker_time_off = self.env.ref("hr_work_entry.l10n_be_work_entry_type_worker_time_off")

        worker = self.create_employee({
            "name": "Wallace Worker",
            "employee_type_id": self.env.ref("l10n_be_hr_payroll.l10n_be_contract_type_be_worker").id,
            "date_version": date(2024, 1, 1),
            "contract_date_start": date(2024, 1, 1),
            "l10n_be_worker_code_id": self.worker_code_id.id,
            "l10n_be_dimona_category": "oth",
        })
        worker.l10n_be_worker_code_id = self.env['l10n.be.worker.code'].search([('dmfa_code', '=', '015')])
        holiday_year = worker.first_contract_date.year

        worker_allocation, _wrong_time_type = self.env["hr.leave.allocation"].create([
            {
                "name": "Worker time off",
                "employee_id": worker.id,
                "work_entry_type_id": worker_time_off.id,
                "number_of_days": 20,
                "date_from": date(holiday_year, 1, 1),
                "date_to": date(holiday_year, 12, 31),
                "state": "confirm",
            },
            # Legal leave is the Employee work entry type, so it must not match for a Worker.
            {
                "name": "Legal leave",
                "employee_id": worker.id,
                "work_entry_type_id": legal_leave.id,
                "number_of_days": 20,
                "date_from": date(holiday_year, 1, 1),
                "date_to": date(holiday_year, 12, 31),
                "state": "confirm",
            },
        ])

        attestation = self.env["l10n.be.holiday.attest"].create({
            "employee_id": worker.id,
            "date_from": date(holiday_year - 1, 1, 1),
            "date_to": date(holiday_year - 1, 12, 31),
            "prev_work_time_rate": 1,
            "prev_work_days_per_week": 5,
            "prev_days_earned": 10,
            "prev_simple_holiday_pay_paid": 1000,
            "prev_double_holiday_pay_paid": 0,
        })

        self.assertEqual(attestation.linkable_allocation_ids, worker_allocation)

    def test_link_existing_allocation_on_create(self):
        """Selecting a candidate on creation links and resizes it instead of creating a new allocation."""
        legal_leave = self.env.ref("hr_work_entry.be_work_entry_type_legal_leave")
        holiday_year = self.employee_georges.first_contract_date.year

        existing_allocation = self.env["hr.leave.allocation"].create({
            "name": "Pre-allocation",
            "employee_id": self.employee_georges.id,
            "work_entry_type_id": legal_leave.id,
            "number_of_days": 20,
            "date_from": date(holiday_year, 1, 1),
            "date_to": date(holiday_year, 12, 31),
            "state": "confirm",
        })

        attestation = self.env["l10n.be.holiday.attest"].create({
            "employee_id": self.employee_georges.id,
            "date_from": date(holiday_year - 1, 1, 1),
            "date_to": date(holiday_year - 1, 12, 31),
            "prev_work_time_rate": 1,
            "prev_work_days_per_week": 5,
            "prev_days_earned": 10,
            "prev_simple_holiday_pay_paid": 1000,
            "prev_double_holiday_pay_paid": 0,
            "allocation_to_link_id": existing_allocation.id,
        })

        self.assertEqual(attestation.leave_allocation_id, existing_allocation)
        self.assertEqual(existing_allocation.number_of_days, attestation.days_to_allocate)
        self.assertEqual(
            self.env["hr.leave.allocation"].search_count([
                ("employee_id", "=", self.employee_georges.id),
                ("work_entry_type_id", "=", legal_leave.id),
                ("state", "!=", "refuse"),
            ]),
            1,
            "Linking an existing allocation must not create a second one.",
        )

    def test_part_time_5_days_per_week_allocation(self):
        """
        A worker on 20 hours/week over 5 days/week (4 hours/day), fully worked all of 2025 with
        no absences, is entitled to the full legal 4 weeks of leave for 2026: 20 days (4 weeks *
        5 days/week) and 80 hours (4 weeks * 20 hours/week), independently of the fact that they
        only work 4 hours/day.
        """
        calendar = self.resource_calendar.copy({
            'name': 'Part-time 20h/week (5 days)',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 8, 'hour_to': 12})
                for day in range(5)
            ],
        })
        employee = self.create_employee({
            'name': 'Part-Time 5 Days',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': calendar.id,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
        })

        wizard = self.env['hr.payroll.alloc.paid.leave'].create({'year': '2025'})
        wizard.alloc_employee_ids = wizard.alloc_employee_ids.filtered(lambda alloc: alloc.employee_id == employee)

        self.assertEqual(wizard.alloc_employee_ids.paid_time_off_to_allocate, 20)
        self.assertEqual(wizard.alloc_employee_ids.hours_to_allocate, 80)

        view = wizard.generate_allocation()
        allocation = self.env['hr.leave.allocation'].search(view['domain'])
        self.assertEqual(allocation.number_of_days, 20)
        self.assertEqual(allocation.number_of_hours, 80)
        self.assertEqual(allocation.date_from, date(2026, 1, 1))
        self.assertEqual(allocation.date_to, date(2026, 12, 31))

    def test_six_days_per_week_allocation(self):
        """
        A worker on 40 hours/week over 6 days/week (~6h40 /day), fully worked all of 2025 with no
        absences, is entitled to the full legal 4 weeks of leave for 2026: 24 days (4 weeks * 6
        days/week, the 6-day-week legal cap) and 160 hours (4 weeks * 40 hours/week).
        """
        calendar = self.resource_calendar.copy({
            'name': '6 days/week, 40h/week',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 8, 'hour_to': 8 + 40 / 6})
                for day in range(6)
            ],
        })
        employee = self.create_employee({
            'name': 'Six Day Week',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': calendar.id,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
        })

        wizard = self.env['hr.payroll.alloc.paid.leave'].create({'year': '2025'})
        wizard.alloc_employee_ids = wizard.alloc_employee_ids.filtered(lambda alloc: alloc.employee_id == employee)

        self.assertEqual(wizard.alloc_employee_ids.paid_time_off_to_allocate, 24)
        self.assertEqual(wizard.alloc_employee_ids.hours_to_allocate, 160)

        view = wizard.generate_allocation()
        allocation = self.env['hr.leave.allocation'].search(view['domain'])
        self.assertEqual(allocation.number_of_days, 24)
        self.assertEqual(allocation.number_of_hours, 160)
        self.assertEqual(allocation.date_from, date(2026, 1, 1))
        self.assertEqual(allocation.date_to, date(2026, 12, 31))

    def test_same_employer_hours_reduction_next_year(self):
        """
        A worker fully worked all of 2025 at 38h/week (5 days/week) for the current employer, then
        moves to a reduced 35h/week (still 5 days/week) contract for 2026 -- no attestation, no
        employer change, just a schedule change at the same employer.

        Capped at the lower of the old and new absolute hours/week -- here the *new*, lower rate --
        this is 4 weeks at 35h/week = 140 hours, i.e. 20 days (140 / (35 / 5) = 140 / 7 hours/day).
        """
        calendar_35 = self.resource_calendar.copy({
            'name': 'Reduced to 35h/week (5 days)',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 8, 'hour_to': 15})
                for day in range(5)
            ],
        })
        employee = self.create_employee({
            'name': 'Hours Reduction Next Year',
            'date_version': date(2022, 1, 1),
            'contract_date_start': date(2022, 1, 1),
            'contract_date_end': date(2025, 12, 31),
            'resource_calendar_id': self.resource_calendar.id,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
        })
        employee.create_version({
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': calendar_35.id,
        })

        wizard = self.env['hr.payroll.alloc.paid.leave'].create({'year': '2025'})
        alloc_employee = wizard.alloc_employee_ids.filtered(lambda a: a.employee_id == employee)

        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 20)
        self.assertEqual(alloc_employee.hours_to_allocate, 140)

    def test_same_employer_hours_increase_next_year(self):
        """
        A worker fully worked all of 2025 at 35h/week (5 days/week) for the current employer, then
        moves to a higher 38h/week (still 5 days/week) contract for 2026 -- no attestation, no
        employer change, just a schedule change at the same employer.

        Capped at the lower of the old and new absolute hours/week -- here the *old*, lower rate --
        this is 4 weeks at 35h/week = 140 hours, i.e. 18 days (140 / (38 / 5) = 140 / 7.6 hours/day
        = 18.42, rounded down to the nearest half-day).
        """
        calendar_35 = self.resource_calendar.copy({
            'name': 'Started at 35h/week (5 days)',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 8, 'hour_to': 15})
                for day in range(5)
            ],
        })
        employee = self.create_employee({
            'name': 'Hours Increase Next Year',
            'date_version': date(2022, 1, 1),
            'contract_date_start': date(2022, 1, 1),
            'contract_date_end': date(2025, 12, 31),
            'resource_calendar_id': calendar_35.id,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
        })
        employee.create_version({
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'contract_date_end': False,
            'resource_calendar_id': self.resource_calendar.id,
        })

        wizard = self.env['hr.payroll.alloc.paid.leave'].create({'year': '2025'})
        alloc_employee = wizard.alloc_employee_ids.filtered(lambda a: a.employee_id == employee)

        self.assertEqual(alloc_employee.paid_time_off_to_allocate, 18)
        self.assertEqual(alloc_employee.hours_to_allocate, 140)
