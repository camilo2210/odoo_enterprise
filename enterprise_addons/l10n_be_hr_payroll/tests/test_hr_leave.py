# Part of Odoo. See LICENSE file for full copyright and licensing details.
import uuid
from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_right_to_legal_leaves')
class TestPayrollRightToLegalLeaves(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setup used by progressive resumption tests
        cls.sick_leave_type = cls.env.ref("hr_work_entry.be_work_entry_type_sick_leave")
        cls.progressive_resumption_type = cls.env.ref(
            "hr_work_entry.l10n_be_work_entry_type_partial_incapacity"
        )
        cls.progressive_resumption_calendar = cls.env['resource.calendar'].create({
            'name': 'Reprise Progressive',
            'company_id': cls.belgian_company.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38,
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {
                    'dayofweek': weekday,
                    'hour_from': 9,
                    'hour_to': 16.6,
                    'work_entry_type_id': cls.progressive_resumption_type.id,
                })
                for weekday in ['0', '1']
            ] + [
                (0, 0, {
                    'dayofweek': weekday,
                    'hour_from': 9,
                    'hour_to': 16.6,
                })
                for weekday in ['2', '3', '4']
            ],
        })

        cls.progressive_employee = cls.create_employee({
            'name': 'Employee Progressive Test',
            'date_version': date(2025, 8, 1),
            'contract_date_start': date(2025, 8, 1),
            'contract_date_end': False,
            'resource_calendar_id': cls.progressive_resumption_calendar.id,
            'l10n_be_scale_seniority': 8,
        })

        progressive_allocation = cls.env['hr.leave.allocation'].create({
            'work_entry_type_id': cls.progressive_resumption_type.id,
            'employee_id': cls.progressive_employee.id,
            'number_of_days': 400,
            'date_from': date(2025, 8, 1),
            'date_to': date(2026, 1, 31),
        })
        progressive_allocation.action_approve()

    def _setup_temporary_unemployment_data(self, is_worker=True):

        relevant_codes = ['086.00', '006.11', '137.00', '152.00', '151.00', '137.20']
        work_entry_types = self.env['hr.work.entry.type'].search([
            ('country_id.code', '=', 'BE'),
            ('code', 'in', relevant_codes),
        ]).grouped('code')

        worker_worker_code = self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00012')
        worker = self.create_employee({
            'name': 'Worker Worker' if is_worker else 'Employee Employee',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
            # Only a worker code makes a blue collar, a white collar has none
            'l10n_be_worker_code_id': worker_worker_code.id if is_worker else False,
            'contract_date_start': date(2025, 1, 1),
        })
        self.assertEqual(bool(worker.version_id.is_worker()), is_worker, msg="Employee is not recognized as expected.")

        public_holiday_type = self.env.ref("hr_work_entry.l10n_be_work_entry_type_bank_holiday")
        context = {
            'skip_allocation_check': True,
            'default_company_id': worker.company_id.id,
        }
        self.env.user.company_id = worker.company_id

        return worker, work_entry_types, public_holiday_type, context

    def test_edrs_activity_not_logged_without_notified_officers(self):
        """
        Create a time off request using a work_entry_type which doesn't have 'Notified Time Off Officers' and assert
        that eDRS activity isn't logged to the chatter.
        """
        work_entry_type_without_notified_officers = self.env['hr.work.entry.type'].create({
            'name': 'Leave Type Without Notified Officers',
            'code': 'Leave Type Without Notified Officers',
            'requires_allocation': False,
            'employee_requests': True,
            'leave_validation_type': 'both',
            'request_unit': 'day',
            'unit_of_measure': 'day',
        })
        leave_request = self.env['hr.leave'].create({
            'name': 'Leave 1 day',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': work_entry_type_without_notified_officers.id,
            'request_date_from': '2024-10-31',
            'request_date_to': '2024-10-31',
        })
        activity = self.env['mail.activity'].search([
            ('res_id', '=', leave_request.id),
            ('res_model', '=', 'hr.leave'),
        ])
        self.assertFalse(activity)

    def test_sick_time_off_without_guaranteed_salary(self):
        """
        Test for long term sickness that the public holiday is overwritten with a sick time off (without guarantee salary),
        and that the time off is correctly linked to the work entry
        """
        sick_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_sick_leave')
        sick_work_entry_type_without_salary = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')
        self.env['hr.leave'].create({
            'name': 'Sick leave',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': sick_work_entry_type.id,
            'request_date_from': datetime(2024, 1, 16),
            'request_date_to': datetime(2024, 9, 19),
        })
        without_salary_sick_leave = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_georges.id),
            ('request_date_from', '=', datetime(2024, 2, 15))
        ])
        self.assertTrue(without_salary_sick_leave)

        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime(2024, 9, 19, 8),
            'date_to': datetime(2024, 9, 19, 16),
            'calendar_id': self.employee_georges.resource_calendar_id.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday').id,
            'count_as': 'absence',
        })

        work_entries_vals = self.employee_georges.generate_work_entries(date(2024, 1, 16), date(2024, 9, 19))
        public_holiday_date_work_entry_vals = next(vals for vals in work_entries_vals if vals['date'] == date(2024, 9, 19))
        self.assertEqual(public_holiday_date_work_entry_vals['work_entry_type_id'], sick_work_entry_type_without_salary)
        self.assertEqual(public_holiday_date_work_entry_vals['leave_ids'], without_salary_sick_leave)

    def test_sick_time_off_without_guaranteed_salary_split_certificates(self):
        """
        Same scenario as test_sick_time_off_without_guaranteed_salary.
        Here the sickness is certified as two separate monthly hr.leave records instead of one continuous leave.
        The public holiday falls on the first day of the second certificate.
        Regression test: the 30-day guaranteed-salary lookback used to compare exact datetimes instead of calendar days.
        The second certificate was wrongly excluded and the public holiday stayed paid.
        """
        sick_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_sick_leave')
        sick_work_entry_type_without_salary = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')

        self.env['hr.leave'].create({
            'name': 'Sick leave - December',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': sick_work_entry_type.id,
            'request_date_from': datetime(2024, 12, 1),
            'request_date_to': datetime(2024, 12, 31),
        })

        january_leave = self.env['hr.leave'].create({
            'name': 'Sick leave - January',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': sick_work_entry_type.id,
            'request_date_from': datetime(2025, 1, 1),
            'request_date_to': datetime(2025, 1, 31),
            'l10n_be_sickness_relapse': True,
        })

        # Company-wide public holiday, not tied to this employee's own calendar_id.
        # Its own clock time can be earlier than the employee's attendance start, same as a real country-wide holiday.
        self.env['resource.calendar.leaves'].create({
            'name': 'Public Holiday',
            'date_from': datetime(2025, 1, 1, 6),
            'date_to': datetime(2025, 1, 1, 15),
            'calendar_id': False,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday').id,
            'count_as': 'absence',
        })

        work_entries_vals = self.employee_georges.generate_work_entries(date(2024, 12, 1), date(2025, 1, 31))
        public_holiday_date_work_entry_vals = next(vals for vals in work_entries_vals if vals['date'] == date(2025, 1, 1))
        self.assertEqual(public_holiday_date_work_entry_vals['work_entry_type_id'], sick_work_entry_type_without_salary)
        self.assertEqual(public_holiday_date_work_entry_vals['leave_ids'], january_leave)

    def test_unpaid_leave_with_public_holiday_ignored(self):
        self.calendar_38h = self.env['resource.calendar'].create({
            'name': 'Standard 38 hours/week',
            'company_id': self.employee_georges.company_id.id,
            'hours_per_day': 7.6,
            'attendance_ids': [(5, 0, 0),
                               (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                               (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                               (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
                        ],
        })
        self.employee_georges.write({'resource_calendar_id': self.calendar_38h.id})
        work_entry_type_public_holiday = self.env['hr.work.entry.type'].create({
            'name': 'Public Holiday',
            'count_as': 'absence',
            'code': 'LEAVETEST500'
        })
        # Public Holiday in the middle of the week.
        public_holiday_be = self.env['resource.calendar.leaves'].create({
        'date_from': datetime(2026, 3, 17),
        'date_to': datetime(2026, 3, 17),
        'work_entry_type_id': work_entry_type_public_holiday.id,
        'calendar_id': self.calendar_38h.id
        })

        public_holiday_be.company_id = self.employee_georges.company_id
        unpaid_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')
        # Unpaid leave for 5 days.
        unpaid_leave = self.env['hr.leave'].create({
        'name': 'Unpaid',
        'request_date_from': datetime(2026, 3, 16),
        'request_date_to': datetime(2026, 3, 20),
        'employee_id': self.employee_georges.id,
        'work_entry_type_id': unpaid_work_entry_type.id,
        })
        # Public holiday should be counted in the leave days.
        self.assertEqual(unpaid_leave.number_of_days, 5.0)

    def test_progressive_resumption_140_days_boundary(self):
        progressive_resumption_start = date(2025, 8, 1)
        day_139 = progressive_resumption_start + timedelta(days=139)
        day_140 = progressive_resumption_start + timedelta(days=140)
        sick_leave_139, sick_leave_140 = self.env['hr.leave'].create([
            {
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'employee_id': self.progressive_employee.id,
                'request_date_from': day_139,
                'request_date_to': day_139,
            }, {
                'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
                'employee_id': self.progressive_employee.id,
                'request_date_from': day_140,
                'request_date_to': day_140,
            }])
        (sick_leave_139 + sick_leave_140).action_approve()
        self.assertEqual(sick_leave_139.work_entry_type_id.code, '122.00')
        self.assertEqual(sick_leave_140.work_entry_type_id.code, '013.00')

    def test_progressive_resumption_relapse_does_not_charge_neutralised_days(self):
        """A relapse of a neutralised sick leave keeps its own full guaranteed-salary budget.

        The origin's days were never charged against the 30-day guarantee in the first place.
        """
        origin = self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': self.progressive_employee.id,
            'request_date_from': date(2025, 8, 6),
            'request_date_to': date(2025, 9, 2),
        })
        origin.action_approve()
        self.assertEqual(origin.work_entry_type_id.code, '122.00')

        relapse = self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': self.progressive_employee.id,
            'request_date_from': date(2025, 12, 20),
            'request_date_to': date(2025, 12, 29),
            'l10n_be_sickness_relapse_origin_leave_id': origin.id,
        })
        relapse.action_approve()
        self.assertEqual(relapse.work_entry_type_id.code, '013.00')
        self.assertEqual(relapse.request_date_to, date(2025, 12, 29),
                         "The whole 10 days stay paid, none split off as unpaid")

    def test_long_term_sickness_cutoff_includes_progressive_resumption(self):
        sick_leave = self.env['hr.leave'].create({
            'work_entry_type_id': self.sick_leave_type.id,
            'employee_id': self.progressive_employee.id,
            'request_date_from': date(2026, 8, 3),
            'request_date_to': date(2026, 8, 3),
        })

        self.assertEqual(
            sick_leave._get_l10n_be_long_term_sick_cutoff_date(),
            date(2026, 8, 1),
        )

    def test_reproduction_progressive_resumption_neutralisation(self):
        """
        Reproduction scenario:
        - Progressive work resumption from 2025-08-01 to 2026-01-31.
        - Sick leaves on 2025-08-06, 2025-12-31, and 2026-01-01.

        Expected worked-day codes:
        - 2025-08-06: 122.00 (without guaranteed salary, within first 20 weeks)
        - 2025-12-31: 013.00 (guaranteed salary, after first 20 weeks and before 2026)
        - 2026-01-01: 122.00 (without guaranteed salary, 2026 rule)
        """
        vals_list = [
            {
                'work_entry_type_id': self.sick_leave_type.id,
                'employee_id': self.progressive_employee.id,
                'request_date_from': sick_day,
                'request_date_to': sick_day,
            }
            for sick_day in [date(2025, 8, 6), date(2025, 12, 31), date(2026, 1, 1)]
        ]

        sick_leaves = self.env['hr.leave'].create(vals_list)
        sick_leaves_by_date_from = {rec.request_date_from: rec for rec in sick_leaves}
        sick_leaves.action_approve()

        self.assertEqual(sick_leaves_by_date_from[date(2025, 8, 6)].work_entry_type_id.code, "122.00")
        self.assertEqual(sick_leaves_by_date_from[date(2025, 12, 31)].work_entry_type_id.code, "013.00")
        self.assertEqual(sick_leaves_by_date_from[date(2026, 1, 1)].work_entry_type_id.code, "122.00")

        work_entry_codes_aug_06 = {
            vals['work_entry_type_id'].code
            for vals in self.progressive_employee.version_ids.generate_work_entries(
                date(2025, 8, 6), date(2025, 8, 6)
            )
        }
        work_entry_codes_dec_31 = {
            vals['work_entry_type_id'].code
            for vals in self.progressive_employee.version_ids.generate_work_entries(
                date(2025, 12, 31), date(2025, 12, 31)
            )
        }
        work_entry_codes_jan_01 = {
            vals['work_entry_type_id'].code
            for vals in self.progressive_employee.version_ids.generate_work_entries(
                date(2026, 1, 1), date(2026, 1, 1)
            )
        }

        self.assertIn("122.00", work_entry_codes_aug_06)
        self.assertNotIn("013.00", work_entry_codes_aug_06)

        self.assertIn("013.00", work_entry_codes_dec_31)
        self.assertNotIn("122.00", work_entry_codes_dec_31)

        self.assertIn("122.00", work_entry_codes_jan_01)
        self.assertNotIn("013.00", work_entry_codes_jan_01)

    def test_ongoing_pre_2026_leave_is_not_reclassified_after_cutoff(self):
        cross_cutoff_leave = self.env['hr.leave'].create({
            'work_entry_type_id': self.sick_leave_type.id,
            'employee_id': self.progressive_employee.id,
            'request_date_from': date(2025, 12, 31),
            'request_date_to': date(2026, 1, 2),
        })
        cross_cutoff_leave.action_approve()

        self.assertEqual(cross_cutoff_leave.work_entry_type_id.code, "013.00")

        work_entry_codes_jan_01 = {
            vals['work_entry_type_id'].code
            for vals in self.progressive_employee.version_ids.generate_work_entries(
                date(2026, 1, 1), date(2026, 1, 1)
            )
        }
        self.assertIn("013.00", work_entry_codes_jan_01)
        self.assertNotIn("122.00", work_entry_codes_jan_01)

    def test_multi_day_leave_be_payroll(self):
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'company_id': self.belgian_company.id,
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 40,
            'hours_per_day': 8,
        })
        self.employee_georges.write({
            'resource_calendar_id': flexible_calendar.id,
        })

        self.belgian_company.resource_calendar_id.company_id = self.belgian_company

        self.env['hr.leave.allocation'].create({
            'name': 'Allocation',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.holiday_work_entry_types.id,
            'number_of_days': 20,
            'date_from': '2026-05-01',
        }).action_approve()

        multi_day_leave = self.env['hr.leave'].create({
            'name': 'Leave',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.holiday_work_entry_types.id,
            'request_date_from': datetime(2026, 5, 8),
            'request_date_to': datetime(2026, 5, 12),
        })

        self.assertEqual(multi_day_leave.number_of_days, 5)

        multi_day_leave.action_approve()

        self.assertEqual(multi_day_leave.state, 'validate')

    def test_temporary_economic_unemployment_for_employee(self):
        single_economic_unemployment = self.env['hr.leave'].create({
            'name': 'Temporary economic unemployment',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_temporary_economic_unemployement_employee').id,
            'request_date_from': datetime(2026, 6, 8),
            'request_date_to': datetime(2026, 6, 8),
        })
        single_economic_unemployment.action_approve()
        self.assertEqual(single_economic_unemployment.state, 'validate')

    def test_employee_economic_unemployment_public_holiday_after_14_days(self):
        """
        Ensure that a public holiday falling after the 14 first calendar days of an economic
        unemployment is not paid by the employer and stays an economic unemployment day.
        """
        employee, work_entry_types, public_holiday_type, context = self._setup_temporary_unemployment_data(
            is_worker=False,
        )
        economic_unemployment_type = work_entry_types['137.20']
        # The national holiday is the 15th calendar day of a leave starting on the 7th of July
        self._create_calendar_leave(public_holiday_type, date(2025, 7, 21), context=context)
        leave = self._create_employee_leave(
            employee, economic_unemployment_type, date(2025, 7, 7), date(2025, 7, 25), context=context,
        )
        leave.action_approve()

        work_entries = [
            we['work_entry_type_id'].code
            for we in employee.generate_work_entries(date(2025, 7, 1), date(2025, 7, 31))
        ]
        # The 15 working days of the leave all remain economic unemployment, the employer pays nothing
        self.assertEqual(work_entries.count('137.20'), 15, "The whole leave should be economic unemployment.")
        self.assertEqual(work_entries.count('006.11'), 0, "No public holiday should be covered by the employer.")

    def test_employee_economic_unemployment_public_holiday_within_14_days(self):
        """
        Ensure that a public holiday falling in the 14 first calendar days of an economic
        unemployment is still covered by the employer.
        """
        employee, work_entry_types, public_holiday_type, context = self._setup_temporary_unemployment_data(
            is_worker=False,
        )
        economic_unemployment_type = work_entry_types['137.20']
        # The national holiday is the 8th calendar day of a leave starting on the 14th of July
        self._create_calendar_leave(public_holiday_type, date(2025, 7, 21), context=context)
        leave = self._create_employee_leave(
            employee, economic_unemployment_type, date(2025, 7, 14), date(2025, 7, 25), context=context,
        )
        leave.action_approve()

        work_entries = {
            we['date']: we['work_entry_type_id'].code
            for we in employee.generate_work_entries(date(2025, 7, 1), date(2025, 7, 31))
        }
        # Only the holiday itself is covered, the 9 other working days stay economic unemployment
        self.assertEqual(work_entries.get(date(2025, 7, 21)), '006.11', "The holiday should be paid by the employer.")
        self.assertEqual(
            list(work_entries.values()).count('137.20'), 9, "The rest of the leave should be economic unemployment.",
        )

    def test_worker_temporary_unemployment_public_holiday_split_leave(self):
        worker, work_entry_types, public_holiday_type, context = self._setup_temporary_unemployment_data()

        # When a worker has a temporary unemployment leave among following ones 137.00, 152.00, 151.00,
        # and there's a public holiday in the middle (006.00),
        # that day must be paid following different rules.
        # To do so, we split the leave into subsegment and replace the 006.00 by another code.
        # Could be either 006.11 (most common) or 086.00

        march_from, march_to = date(2025, 3, 1), date(2025, 3, 31)
        march_ph_date = date(2025, 3, 20)  # Friday
        before_entries = worker.generate_work_entries(march_from, march_to)

        self._create_calendar_leave(public_holiday_type, march_ph_date)
        self._create_employee_leave(worker, work_entry_types['137.00'], march_from, march_to, context=context)

        after_entries = {we['date']: we['work_entry_type_id'].code for we in
                         worker.generate_work_entries(march_from, march_to)}

        self.assertEqual(list(after_entries.values()).count('137.00'), len(before_entries) - 1)
        self.assertEqual(after_entries.get(march_ph_date), '006.11')

    def test_worker_temporary_unemployment_public_holiday_correct_leave_attribution(self):

        # On the 21st of April, the amount of temporary unemployment day of the worker
        # makes so that the employer can allocate one day without ONSS (086.00)
        # On the 29nth of April, the amount of temporary unemployment does not allow to allocate
        # a second day without ONSS, so we allocate a LEAVE207.

        worker, work_entry_types, public_holiday_type, context = self._setup_temporary_unemployment_data()

        # March and April
        leave_from, leave_to = date(2025, 3, 1), date(2025, 4, 30)
        april_ph_dates = [
            date(2025, 4, 21),  # Monday    -> 086.00
            date(2025, 4, 29),  # Tuesday   -> 006.11
        ]

        for ph_date in april_ph_dates:
            self._create_calendar_leave(public_holiday_type, ph_date)
        self._create_employee_leave(worker, work_entry_types['137.00'], leave_from, leave_to, context=context)

        april_entries = {
            we['date']: we['work_entry_type_id'].code
            for we in worker.generate_work_entries(leave_from, leave_to)
        }

        self.assertEqual(list(april_entries.values()).count('086.00'), 1)
        self.assertEqual(list(april_entries.values()).count('006.11'), 1)
        self.assertEqual(list(april_entries.values()).count('137.00'), 41)
        self.assertEqual(april_entries.get(date(2025, 4, 21)), '086.00')
        self.assertEqual(april_entries.get(date(2025, 4, 29)), '006.11')

    def test_worker_temporary_unemployment_public_holiday_straddling_year(self):
        worker, work_entry_types, public_holiday_type, context = self._setup_temporary_unemployment_data()

        # This test makes sure that the straddling year edge case is handled.
        # On the 5th of December, the quota has not been reached for one 086.00.
        # On 1st of January 2026, the quota could be reached but the counter resets with the passage into the next year.
        # So we apply LEAVE207.

        straddling_from, straddling_to = date(2025, 12, 1), date(2026, 1, 31)
        dec_ph_date = date(2025, 12, 25)  # Thursday
        jan_ph_date = date(2026, 1, 1)  # Thursday
        before_entries = worker.generate_work_entries(straddling_from, straddling_to)

        self._create_calendar_leave(public_holiday_type, dec_ph_date)
        self._create_calendar_leave(public_holiday_type, jan_ph_date)
        self._create_employee_leave(worker, work_entry_types['137.00'], straddling_from, straddling_to,
                                    context=context)

        year_end_entries = {we['date']: we['work_entry_type_id'].code for we in
                            worker.generate_work_entries(straddling_from, straddling_to)}

        self.assertEqual(list(year_end_entries.values()).count('006.11'), 2)
        self.assertEqual(list(year_end_entries.values()).count('137.00'), len(before_entries) - 2)
        self.assertEqual(list(year_end_entries.values()).count('137.00'), 43)
        self.assertEqual(year_end_entries.get(dec_ph_date), '006.11')
        self.assertEqual(year_end_entries.get(jan_ph_date), '006.11')

    def test_worker_temporary_unemployment_public_holiday_mixed_types(self):
        worker, work_entry_types, public_holiday_type, context = self._setup_temporary_unemployment_data()

        # This test is about mixing 137.00, 152.00, 151.00 as they all increase the temporary unemployment day count

        leave_from, leave_to = date(2025, 3, 1), date(2025, 4, 30)
        april_ph_date = date(2025, 4, 21)  # Monday    -> Should be 086.00

        self._create_calendar_leave(public_holiday_type, april_ph_date)
        self._create_employee_leave(worker,
                                    work_entry_types['137.00'],
                                    date(2025, 3, 1),
                                    date(2025, 3, 20),
                                    context=context)
        self._create_employee_leave(worker,
                                    work_entry_types['151.00'],
                                    date(2025, 3, 21),
                                    date(2025, 4, 10),
                                    context=context)
        self._create_employee_leave(worker,
                                    work_entry_types['152.00'],
                                    date(2025, 4, 11),
                                    date(2025, 4, 30),
                                    context=context)

        march_april_entries = {
            we['date']: we['work_entry_type_id'].code
            for we in worker.generate_work_entries(leave_from, leave_to)
        }

        self.assertTrue(list(march_april_entries.values()).count('152.00') > 0)
        self.assertTrue(list(march_april_entries.values()).count('151.00') > 0)
        self.assertTrue(list(march_april_entries.values()).count('137.00') > 0)

        self.assertEqual(march_april_entries.get(date(2025, 4, 21)), '086.00')

    def test_without_certificate_limited_to_one_day(self):
        """ Only the first day of a sick time off may be flagged without certificate:
        longer requests are blocked and the warning's action splits them. """
        option = self.env.ref('l10n_be_hr_payroll.MISSING_CERTIFICATE')
        warning_name = 'Wrong usage of option "Without certificate"'

        employee = self.create_employee({
            'name': 'Employee Without Certificate',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
        })

        leave = self._create_employee_leave(employee, self.sick_leave_type, date(2026, 3, 2), date(2026, 3, 4))
        leave.category_options_ids = option

        cards = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards([], block_payslips=True, include_model_warnings=True)
        self.assertTrue(any(leave in card['warning_records'] for card in cards if card['name'] == warning_name), "Warning should block the payslips")

        leave.action_l10n_be_correct_without_certificate()

        leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)], order='request_date_from')

        self.assertEqual(leaves.mapped('number_of_days'), [1.0, 2.0])
        self.assertEqual(leaves[0], leave, "The first day stays on the original request")
        self.assertIn(option, leaves[0].category_options_ids)
        self.assertNotIn(option, leaves[1].category_options_ids)

        cards = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards([], block_payslips=True, include_model_warnings=True)
        self.assertFalse([card for card in cards if card['name'] == warning_name], "The split requests respect the rule")

    @freeze_time('2026-06-15')
    def test_without_certificate_yearly_limit(self):
        """ At most 2 days per calendar year may be taken without certificate. """
        option = self.env.ref('l10n_be_hr_payroll.MISSING_CERTIFICATE')
        warning_name = 'Too many days without certificate'

        employee = self.create_employee({
            'name': 'Employee Yearly Certificate',
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
        })

        leaves = self.env['hr.leave']
        for month in (2, 4):
            leave = self._create_employee_leave(employee, self.sick_leave_type, date(2026, month, 3), date(2026, month, 3))
            leave.category_options_ids = option
            leaves |= leave

        cards = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards([], block_payslips=True, include_model_warnings=True)
        self.assertFalse([card for card in cards if card['name'] == warning_name], "2 days without certificate are allowed")

        leave = self._create_employee_leave(employee, self.sick_leave_type, date(2026, 6, 3), date(2026, 6, 3))
        leave.category_options_ids = option
        leaves |= leave

        cards = self.env['hr.payroll.warning'].get_payroll_dashboard_warning_cards([], block_payslips=True, include_model_warnings=True)
        flagged = [card for card in cards if card['name'] == warning_name]
        self.assertTrue(flagged, "A 3rd day without certificate should block the payslips")
        self.assertEqual(flagged[0]['warning_records'], leaves, "Every day contributing to the excess is flagged")

    def _create_employee_leave(self, employee, work_entry_type, date_from, date_to, name=None, context=None):
        if name is None:
            name = 'Employee leave ' + uuid.uuid4().hex

        ctx = context or {}
        return self.env['hr.leave'].with_context(**ctx).create({
            'name': name,
            'employee_id': employee.id,
            'resource_calendar_id': employee.resource_calendar_id.id,
            'work_entry_type_id': work_entry_type.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
        })

    def _create_calendar_leave(self, work_entry_type, date_from, date_to=None, calendar=False, name=None, context=None):
        if name is None:
            name = f'Calendar leave {uuid.uuid4().hex}'
        if date_to is None:
            date_to = datetime.combine(date_from, time.max)

        if isinstance(date_from, date):
            date_from = datetime.combine(date_from, time.min)
        if isinstance(date_to, date):
            date_to = datetime.combine(date_to, time.max)

        ctx = context or {}
        return self.env['resource.calendar.leaves'].with_context(**ctx).create({
            'name': name,
            'date_from': date_from,
            'date_to': date_to,
            'calendar_id': calendar.id if calendar else False,
            'work_entry_type_id': work_entry_type.id,
        })

    def test_no_warning_for_sick_leave_within_guaranteed_salary(self):
        """ Georges is a regular employee (not a "worker"): a sick leave staying within the 30-day guaranteed
        salary period keeps the original 013.00 work entry type, so no warning should be raised. """
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 2, 2),
            'request_date_to': date(2026, 2, 6),
        })
        self.assertFalse(any('This time off will be split into' in val['message'] for _, val in leave.issues.items()) if leave.issues else False)
        self.assertFalse(any('This time off will be entirely replaced with' in val['message'] for _, val in leave.issues.items()) if leave.issues else False)

    def test_warning_for_sick_leave_after_guaranteed_salary(self):
        """ A sick leave crossing the 30-day guaranteed salary threshold should warn that it will be split
        between 013.00 (paid) and the unpaid sick work entry type once validated. """
        unpaid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 2, 2),
            'request_date_to': date(2026, 3, 20),
        })
        self.assertTrue(any('This time off will be split into' in val['message'] for _, val in leave.issues.items()))
        self.assertTrue(any('013.00' in val['message'] for _, val in leave.issues.items()))
        self.assertTrue(any('122.00' in val['message'] for _, val in leave.issues.items()))

        # Once validated, the single leave should effectively be split into two leaves matching the warning.
        leave._action_validate()
        all_leaves = self.env['hr.leave'].search(
            [('employee_id', '=', self.employee_georges.id)]
        ).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 2)
        self.assertEqual(all_leaves[0].work_entry_type_id.code, '013.00')
        self.assertEqual(all_leaves[1].work_entry_type_id, unpaid_type)

    def test_warning_for_sick_leave_not_saved_yet(self):
        """
        Ensure that the split warning is already shown on a time off request that is not saved yet.
        """
        leave = self.env['hr.leave'].new({
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 2, 2),
            'request_date_to': date(2026, 3, 20),
        })
        messages = [val['message'] for val in (leave.issues or {}).values()]
        self.assertTrue(
            any('This time off will be split into' in message for message in messages),
            "The split warning should be shown before the request is saved",
        )

    def test_warning_entirely_replaced_for_worker_short_sick_leave(self):
        """ For a "worker" employee, sick leave paid during the first week uses a different work entry type
        (010.00) than the requested 013.00, so the warning announces a full replacement. """
        worker_worker_code = self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00012')
        worker = self.create_employee({
            'name': 'Warning Worker',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'l10n_be_worker_code_id': worker_worker_code.id,
            'contract_date_start': date(2020, 1, 1),
            'date_version': date(2020, 1, 1),
        })
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': worker.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 2, 2),
            'request_date_to': date(2026, 2, 4),
        })
        self.assertTrue(any('This time off will be entirely replaced with' in val['message'] for _, val in leave.issues.items()))
        self.assertTrue(any('010.00' in val['message'] for _, val in leave.issues.items()))
        self.assertTrue(any('Guaranted weekly wage illness' in val['message'] for _, val in leave.issues.items()))

    def test_no_warning_for_non_eligible_work_entry_type(self):
        """ The warning only applies to specific work entry types (sick leave, work accident,
        economic unemployment); other leave types never raise it. """
        other_work_entry_type = self.env['hr.work.entry.type'].create({
            'name': 'Other Leave',
            'code': 'OTHERBE',
            'requires_allocation': False,
        })
        leave = self.env['hr.leave'].with_context(leave_fast_create=True).create({
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': other_work_entry_type.id,
            'request_date_from': date(2026, 2, 2),
            'request_date_to': date(2026, 3, 20),
        })
        self.assertFalse(any('This time off will be split into' in val['message'] for _, val in leave.issues.items()) if leave.issues else False)
        self.assertFalse(any('This time off will be entirely replaced with' in val['message'] for _, val in leave.issues.items()) if leave.issues else False)

    def test_8_week_consecutive_sick_leave_created_activity(self):
        """
        Test that only one activity is created for a series of relapsing sick leaves spanning more than 8 weeks,
        Activity's deadline should be set to 6 months after the first sick leave in that series.
        """
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 0, "Employee should not have any sick leave activities yet.")

        sick_leave_1 = self.env['hr.leave'].create({
            'name': 'Sick leave 1',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'request_date_from': datetime(2026, 1, 1),
            'request_date_to': datetime(2026, 1, 15),
        })
        # No activity created yet
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 0, "Employee should not have any sick leave activities yet.")

        sick_leave_2 = self.env['hr.leave'].create({
            'name': 'Sick leave 2',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'l10n_be_sickness_relapse_origin_leave_id': sick_leave_1.id,
            'request_date_from': datetime(2026, 1, 16),
            'request_date_to': datetime(2026, 3, 1),
        })
        # Activity is created
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 1, "Employee should have one sick leave activities.")
        self.assertEqual(employee_activities[-1].date_deadline, sick_leave_1.request_date_from + relativedelta(months=6), "Activity deadline should be 6 months after the first sick leave in the series.")

        self.env['hr.leave'].create({
            'name': 'Sick leave 3',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'l10n_be_sickness_relapse_origin_leave_id': sick_leave_2.id,
            'request_date_from': datetime(2026, 3, 3),
            'request_date_to': datetime(2026, 3, 12),
        })
        # No activity created yet due to present activity
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 1, "Employee should have one sick leave activities.")

    def test_8_week_consecutive_sick_leave_automatic_relapse(self):
        """Consecutive sick leaves create one activity through automatic relapse linking."""
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 0, "Employee should not have any sick leave activities yet.")

        sick_leave_1 = self.env['hr.leave'].create({
            'name': 'Sick leave 1',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'request_date_from': datetime(2026, 1, 1),
            'request_date_to': datetime(2026, 1, 15),
        })
        # The first sickness is shorter than eight weeks.
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 0, "Employee should not have any sick leave activities yet.")

        self.env['hr.leave'].create({
            'name': 'Sick leave 2',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'request_date_from': datetime(2026, 1, 16),
            'request_date_to': datetime(2026, 3, 1),
        })
        # Consecutive leaves are linked automatically.
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 1, "Employee should have one sick leave activity.")

        self.env['hr.leave'].create({
            'name': 'Sick leave 3',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'l10n_be_sickness_relapse_origin_leave_id': sick_leave_1.id,
            'request_date_from': datetime(2026, 3, 3),
            'request_date_to': datetime(2026, 3, 12),
        })
        # The existing activity is kept when another relapse is added.
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 1, "Employee should have one sick leave activity.")

    def test_8_week_non_consecutive_sick_leave_created_activity(self):
        """
        Test that only one activity is created for a series of relapsing sick leaves spanning more than 8 weeks,
        Activity's deadline should be set to 6 months after the first sick leave in that series.
        """
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 0, "Employee should not have any sick leave activities yet.")

        sick_leave_1 = self.env['hr.leave'].create({
            'name': 'Sick leave 1',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'request_date_from': datetime(2026, 1, 1),
            'request_date_to': datetime(2026, 2, 15),
        })
        # No activity created yet
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 0, "Employee should not have any sick leave activities yet.")

        self.env['hr.leave'].create({
            'name': 'Sick leave 2',
            'employee_id': self.employee_georges.id,
            'work_entry_type_id': self.sick_leave_type.id,
            'l10n_be_sickness_relapse_origin_leave_id': sick_leave_1.id,
            'request_date_from': datetime(2026, 3, 16),
            'request_date_to': datetime(2026, 4, 15),
        })
        # Activity is created
        employee_activities = self.employee_georges.activity_ids.filtered(lambda a: a.technical_usage == 'l10n_be_hr_payroll_8_weeks_STO')
        self.assertEqual(len(employee_activities), 1, "Employee should have one sick leave activities.")
        self.assertEqual(employee_activities[-1].date_deadline, sick_leave_1.request_date_from + relativedelta(months=6), "Activity deadline should be 6 months after the first sick leave in the series.")
