# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, time

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestAnalyticLine(TestCommonTimesheet):
    def test_check_timesheet_unit_amount(self):
        AccountAnalyticLine = self.env['account.analytic.line'].with_context(default_name='/')
        timesheet, analytic_line = AccountAnalyticLine.create([
            {
                'project_id': self.project_customer.id,
                'employee_id': self.empl_employee.id,
                'unit_amount': 1,
            },
            {
                'account_id': self.project_customer.account_id.id,
                'unit_amount': 1000000,
            },
        ])
        for value in (1000000, -1000000):
            with self.assertRaisesRegex(UserError, "You can't encode numbers with more than six digits."):
                AccountAnalyticLine.create({
                    'project_id': self.project_customer.id,
                    'employee_id': self.empl_employee.id,
                    'unit_amount': value,
                })
            with self.assertRaisesRegex(UserError, "You can't encode numbers with more than six digits."):
                timesheet.unit_amount = value

        self.assertEqual(analytic_line.unit_amount, 1000000, "The user can enter a number with more than 6 digits for the analytic line which is not a timesheet.")
        analytic_line.unit_amount = 1000005
        self.assertEqual(analytic_line.unit_amount, 1000005, "The user can always alter the analytic to put the number he wants since it is not a timesheet.")

    def test_grid_unavailability_with_current_user_being_employee_in_multiple_companies(self):
        # Create employee in two companies for current user
        self.env['hr.employee'].create({
            'user_id': self.env.user.id,
            'company_id': self.env.company.id
        })
        second_company = self.env['res.company'].create({
            'name': 'Second company',
        })
        self.env['hr.employee'].create({
            'user_id': self.env.user.id,
            'company_id': second_company.id
        })
        self.assertTrue(self.env['account.analytic.line'].grid_unavailability('2020-10-10', '2020-10-12'))

    def test_timesheet_unavailabilities(self):
        """
        Test that unavailabilities are based on current user's calendar if no groupby is provided
        """

        calendar_emp = self.env['resource.calendar'].create({
            'name': 'Monday Only Calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 16, 'day_period': 'morning'}),
            ],
        })

        test_user = self.env['res.users'].create({
            'name': 'Test Employee User',
            'login': 'test_emp_user',
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })

        self.env['hr.employee'].create({
            'name': 'Test Employee',
            'user_id': test_user.id,
            'resource_calendar_id': calendar_emp.id,
        })

        start_date = '2026-04-14'
        end_date = '2026-04-15'

        unavailabilities = self.env['account.analytic.line'].with_user(test_user).with_context(get_current_user_unavailable_dates=True).grid_unavailability(
            start_date=start_date,
            end_date=end_date,
            groupby=''
        )

        self.assertIn(False, unavailabilities, "The result should contain the key False when no groupby is used.")
        unavailable_dates = unavailabilities[False]
        expected_dates = [date(2026, 4, 14), date(2026, 4, 15)]

        for d in expected_dates:
            self.assertIn(d, unavailable_dates, f"Date {d} should be marked as unavailable for this employee.")

    def test_grid_unavailability_respects_employee_working_schedule(self):
        """ Test that timesheet grid shows public holidays from employee's working schedule, not company default.
            Test Cases:
            ===========
            1) Create two working schedules with different public holidays
            2) Set company default to one schedule, employee to another
            3) Test "My Timesheets" view shows employee's holidays
        """
        schedule_35h, schedule_40h = self.env['resource.calendar'].create([
            {
                'name': 'Schedule 35 hours/week',
                'hours_per_day': 7.0,
                'attendance_ids': [(0, 0, {
                    'dayofweek': '0', 'hour_from': 8, 'hour_to': 15
                })],
            },
            {
                'name': 'Schedule 40 hours/week',
                'hours_per_day': 8.0,
                'attendance_ids': [(0, 0, {
                    'dayofweek': '0', 'hour_from': 8, 'hour_to': 16
                })],
            },
        ])

        self.env.company.resource_calendar_id = schedule_40h

        employee_holiday_date = date(2025, 6, 30)  # Employee's public holiday (35h schedule)
        company_holiday_date = date(2025, 7, 7)   # Company's public holiday (40h schedule)

        self.env['resource.calendar.leaves'].create([
            {
                'name': 'Employee Public Holiday (35h)',
                'calendar_id': schedule_35h.id,
                'date_from': datetime.combine(employee_holiday_date, time.min),
                'date_to': datetime.combine(employee_holiday_date, time.max),
            },
            {
                'name': 'Company Public Holiday (40h)',
                'calendar_id': schedule_40h.id,
                'date_from': datetime.combine(company_holiday_date, time.min),
                'date_to': datetime.combine(company_holiday_date, time.max),
            },
        ])

        self.empl_employee.resource_calendar_id = schedule_35h

        analytic_line_model = self.env['account.analytic.line'].with_user(self.empl_employee.user_id).with_context(get_current_user_unavailable_dates=True)
        my_timesheets_result = analytic_line_model.grid_unavailability('2025-06-28', '2025-07-12')
        my_unavailable_days = my_timesheets_result.get(False, [])

        self.assertIn(employee_holiday_date, my_unavailable_days,
            "My Timesheets should show employee's assigned schedule public holiday")
        self.assertNotIn(company_holiday_date, my_unavailable_days,
            "My Timesheets should NOT show company default schedule holiday when employee has different schedule")

    def test_grid_unavailability_does_not_include_other_company_leaves(self):
        """ Test that public holidays from other companies are excluded in the timesheet grid view.

            Test Cases:
            ===========
            1) Create a new company, Company B.
            2) Create a public holiday for Company B only.
            3) Fetch unavailability data for the employee in the current company ('YourCompany').
            4) Verify that the holiday from Company B is not included in the result.
        """

        company_b = self.env['res.company'].create({'name': 'Test Company B'})

        # Create the global holiday that belongs ONLY to Company B.
        holiday_date = date(2025, 6, 26)
        holiday = self.env['resource.calendar.leaves'].with_company(company_b).create({
            'name': 'Holiday for Company B Only',
            'count_as': 'absence',
            'date_from': datetime.combine(holiday_date, time.min),
            'date_to': datetime.combine(holiday_date, time.max),
        })
        self.assertEqual(holiday.company_id, company_b, "The holiday should belong to Company B")

        analytic_line_model = self.env['account.analytic.line'].with_user(self.user_manager)
        result = analytic_line_model.grid_unavailability('2025-06-22', '2025-06-28', 'employee_id', res_ids=[self.empl_employee.id])[False]

        self.assertNotIn(holiday_date, result, "The company-wide leaves should NOT include a holiday from another company.")
