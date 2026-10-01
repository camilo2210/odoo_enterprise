# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta

from freezegun import freeze_time

from odoo.tests import HttpCase, tagged

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet
from odoo.addons.hr.tests.test_utils import get_admin_employee


@tagged('-at_install', 'post_install')
class TestRecordTime(TestCommonTimesheet, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env['project.project'].create({
            'name': 'Test Project'
        })

        cls.admin_employee = get_admin_employee(cls.env)

    def test_timesheet_overtime(self):
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 40,
            'hours_per_day': 8
        })
        self.empl_employee.write({
            'resource_calendar_id': flexible_calendar.id,
        })
        # Get this week's Monday (or next Monday if today is Sunday)
        relevant_monday = date.today() + timedelta(
            days=-date.today().weekday() + (7 if date.today().weekday() == 6 else 0)
        )
        timesheets = self.env['account.analytic.line'].create([
            {
                'name': f"Test Timesheet {i+1}",
                'project_id': self.project_customer.id,
                'task_id': self.task1.id,
                'date': relevant_monday - timedelta(days=i),
                'unit_amount': 3.0 + i,
                'employee_id': self.empl_employee.id,
            }
            for i in range(8)
        ])

        self.start_tour('/odoo', 'timesheet_overtime_hour_encoding', login=self.user_employee.login, timeout=100)

        timesheets[6].write({'unit_amount': 0.0})

        self.env['res.config.settings'].create({'timesheet_encode_method': 'days'}).execute()
        self.start_tour('/odoo', 'timesheet_overtime_day_encoding', login=self.user_employee.login, timeout=100)

    def test_timesheet_availabilty_days(self):
        # Create company
        company = self.env['res.company'].create({'name': 'New Test Company'})

        # Create user
        test_user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user',
            'email': 'test@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            'company_ids': [(6, 0, [company.id])],
            'company_id': company.id,
        })

        # Create employee linked to user
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 8,
            'hours_per_day': 8,
            'company_id': company.id,
        })
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'user_id': test_user.id,
            'company_id': company.id,
            'resource_calendar_id': flexible_calendar.id,
        })

        # Ensure company calendar is NOT flexible (to avoid global override)
        company.resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'Company Calendar (Rigid)',
        })

        # Call grid_unavailability() with the employee
        unavailable_days = self.env['account.analytic.line'].with_user(test_user).with_company(company).grid_unavailability(
            date.today(),
            date.today() + timedelta(days=7)
        )

        # No unavailable days for flexible schedule in my Timesheet
        self.assertFalse(len(unavailable_days[False]))

        # Call again, this time with groupby='employee_id'
        unavailable_days = self.env['account.analytic.line'].with_company(company).grid_unavailability(
            date.today(),
            date.today() + timedelta(days=7),
            groupby='employee_id',
            res_ids=[employee.id]
        )

        # Company availability
        self.assertTrue(len(unavailable_days[False]))
        self.assertFalse(unavailable_days[employee.id])

    def test_timer_onchange_project_prefills_recent_task(self):
        """Selecting a project in the timer prefills the most recent eligible task the user logged time on."""
        Timesheet = self.env['account.analytic.line'].with_user(self.user_employee)
        timesheet = self.env['account.analytic.line'].create({
            'name': '/',
            'date': date.today() - timedelta(days=60),
            'project_id': self.project_customer.id,
            'task_id': self.task1.id,
            'employee_id': self.empl_employee.id,
            'unit_amount': 1.0,
        })

        line = Timesheet.with_context(timesheet_timer_search=True).new({'project_id': self.project_customer.id})
        line._onchange_project_id()
        self.assertFalse(line.task_id, "The timer should not prefill a task that is no longer relevant")

        timesheet.date = date.today()
        line = Timesheet.with_context(timesheet_timer_search=True).new({'project_id': self.project_customer.id})
        line._onchange_project_id()
        self.assertEqual(line.task_id, self.task1,
                         "The timer should prefill the task the user recently logged time on")

        line = Timesheet.new({'project_id': self.project_customer.id})
        line._onchange_project_id()
        self.assertFalse(line.task_id, "Selecting a project only prefills a task in the timer")

        timesheet.task_id = False
        line = Timesheet.with_context(timesheet_timer_search=True).new({'project_id': self.project_customer.id})
        line._onchange_project_id()
        self.assertFalse(line.task_id, "The timer should prefill no task when the last timesheet has none")

    @freeze_time('2026-07-13 00:30:00')  # 00:30 UTC == 20:30 the previous day in America/Guadeloupe (UTC-4)
    def test_systray_timer_survives_utc_midnight(self):
        """A running timer stays visible in the systray after the server's UTC clock
        passes midnight while it is still the previous day in the user's timezone."""
        self.user_employee.tz = 'America/Guadeloupe'
        self.user_employee.password = self.user_employee.login
        self.authenticate(self.user_employee.login, self.user_employee.login)
        running = self.env['account.analytic.line'].create({
            'name': '/',
            'project_id': self.project_customer.id,
            'employee_id': self.empl_employee.id,
            'date': date(2026, 7, 12),
            'unit_amount': 0.0,
        })
        result = self.make_jsonrpc_request('/timesheet_grid/timesheet_systray_user_data', params={})
        self.assertIn(running.id, [ts['id'] for ts in result['timesheets']['records']])
