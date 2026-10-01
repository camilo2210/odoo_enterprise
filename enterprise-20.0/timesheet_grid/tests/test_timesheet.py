# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields, Command
from odoo.addons.mail.tests.common import MockEmail
from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet
from odoo.exceptions import AccessError, RedirectWarning, UserError
from odoo.tests import tagged, Form, freeze_time


@freeze_time(datetime(2021, 4, 1) + timedelta(hours=12, minutes=21))
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestTimesheetValidation(TestCommonTimesheet, MockEmail):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = fields.Date.today()
        cls.timesheet1 = cls.env['account.analytic.line'].with_user(cls.user_employee).create({
            'name': "my timesheet 1",
            'project_id': cls.project_customer.id,
            'task_id': cls.task1.id,
            'date': today - timedelta(days=1),
            'unit_amount': 2.0,
        })
        cls.timesheet2 = cls.env['account.analytic.line'].with_user(cls.user_employee).create({
            'name': "my timesheet 2",
            'project_id': cls.project_customer.id,
            'task_id': cls.task2.id,
            'date': today - timedelta(days=1),
            'unit_amount': 3.11,
        })

    def test_generate_timesheet_after_validation(self):
        self.env.company.timesheet_encode_uom_id = self.env.ref('uom.product_uom_day')
        Timesheet = self.env['account.analytic.line']
        today = fields.Date.today()
        timesheet_entry = Timesheet.with_user(self.user_manager).create({
            'project_id': self.project_customer.id,
            'task_id': self.task1.id,
            'name': 'my first timesheet',
            'unit_amount': 4.0,
            'employee_id': self.empl_manager.id,
        })
        timesheet_entry.with_user(self.user_manager).action_validate_timesheet()
        timesheet_domain = [('employee_id', '=', self.empl_manager.id), ('date', '=', today)]
        sheet_count = Timesheet.search_count(timesheet_domain)
        self.assertEqual(sheet_count, 1)

        Timesheet.with_user(self.user_manager).grid_update_cell([('id', '=', timesheet_entry.id)], 'unit_amount', 2.0)
        timesheet_entrys = Timesheet.search(timesheet_domain)
        self.assertEqual(len(timesheet_entrys), 2, "After the timesheet is validated, a new timesheet entry should be generated.")

        Timesheet.with_user(self.user_manager).grid_update_cell([('id', 'in', timesheet_entrys.ids)], 'unit_amount', 5.0)
        sheet_count1 = Timesheet.search(timesheet_domain)
        self.assertEqual(len(sheet_count1), 2, "Modify non-validated timesheet entries if there's any.")

    def test_timesheet_validation_user(self):
        """ Employee record its timesheets and Officer validate them. Then try to modify/delete it and get Access Error """
        # Officer validate timesheet of 'user_employee' through wizard
        timesheet_to_validate = self.timesheet1 | self.timesheet2
        timesheet_to_validate.with_user(self.user_manager).action_validate_timesheet()

        # Check timesheets 1 and 2 are validated
        self.assertTrue(self.timesheet1.validated)
        self.assertTrue(self.timesheet2.validated)

        # Employee can not modify validated timesheet
        with self.assertRaises(AccessError):
            self.timesheet1.with_user(self.user_employee).write({'unit_amount': 5})
        # Employee can not delete validated timesheet
        with self.assertRaises(AccessError):
            self.timesheet2.with_user(self.user_employee).unlink()

        # Employee can not create new timesheet before last validation date
        with self.assertRaises(AccessError):
            last_month = datetime.now() - relativedelta(months=1)
            self.env['account.analytic.line'].with_user(self.user_employee).create({
                'name': "my timesheet 3",
                'project_id': self.project_customer.id,
                'task_id': self.task2.id,
                'date': last_month,
                'unit_amount': 2.5,
            })

        # Employee can still create timesheet after validated date
        next_month = datetime.now() + relativedelta(months=1)
        timesheet4 = self.env['account.analytic.line'].with_user(self.user_employee).create({
            'name': "my timesheet 4",
            'project_id': self.project_customer.id,
            'task_id': self.task2.id,
            'date': next_month,
            'unit_amount': 2.5,
        })
        # And can still update non validated timesheet
        timesheet4.write({'unit_amount': 7})

    def test_timesheet_validation_manager(self):
        """ Officer can see timesheets and modify the ones of other employees """
       # Officer validate timesheet of 'user_employee' through wizard
        timesheet_to_validate = self.timesheet1 | self.timesheet2
        timesheet_to_validate.with_user(self.user_manager).action_validate_timesheet()
        # manager modify validated timesheet
        self.timesheet1.with_user(self.user_manager).write({'unit_amount': 5})

    def _test_next_date(self, now, result, delay, interval):
        with self.mock_datetime_and_now(now):
            self.user_manager.company_id.write({
                'timesheet_mail_interval': interval,
                'timesheet_mail_delay': delay,
            })

            self.assertEqual(result, self.user_manager.company_id.timesheet_mail_nextdate)

    def test_timesheet_next_date_reminder_neg_delay(self):

        result = datetime(2020, 4, 23, 8, 8, 15)
        now = datetime(2020, 4, 22, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 4, 30, 8, 8, 15)
        now = datetime(2020, 4, 23, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 4, 24, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 4, 25, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 4, 27, 8, 8, 15)
        now = datetime(2020, 4, 26, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

        result = datetime(2020, 5, 28, 8, 8, 15)
        now = datetime(2020, 4, 27, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 4, 28, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 4, 29, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

        result = datetime(2020, 2, 27, 8, 8, 15)
        now = datetime(2020, 2, 26, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 3, 5, 8, 8, 15)
        now = datetime(2020, 2, 27, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 2, 28, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")
        now = datetime(2020, 2, 29, 8, 8, 15)
        self._test_next_date(now, result, -3, "weeks")

        result = datetime(2020, 2, 26, 8, 8, 15)
        now = datetime(2020, 2, 25, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

        result = datetime(2020, 3, 28, 8, 8, 15)
        now = datetime(2020, 2, 26, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 2, 27, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")
        now = datetime(2020, 2, 28, 8, 8, 15)
        self._test_next_date(now, result, -3, "months")

    def test_working_hours_for_employees(self):
        company = self.env['res.company'].create({'name': 'My_Company'})
        uom_day = self.env.ref('uom.product_uom_day')
        employee = self.env['hr.employee'].with_company(company).create({
            'name': 'Juste Leblanc',
            'user_id': self.user_manager.id,
            'create_date': date(2021, 1, 1),
        })
        working_hours = employee.get_timesheet_and_working_hours_for_employees('2021-12-01', '2021-12-31')
        self.assertEqual(working_hours[employee.id]['units_to_work'], 184.0, "Number of hours should be 23d * 8h/d = 184h")

        working_hours = employee.get_timesheet_and_working_hours('2021-12-01', '2021-12-31')
        self.assertEqual(working_hours[employee.id]['working_hours'], 184.0, "Number of hours should be 23d * 8h/d = 184h")

        # Switch timesheet encoding to days and simulate a translated UoM
        # to ensure day detection does not rely on translated names.
        company.timesheet_encode_uom_id = uom_day.id
        self.env['res.lang']._activate_lang('fr_FR')
        uom_day.with_context(lang='fr_FR').name = 'Jours'

        working_hours = employee.with_context(lang='fr_FR').get_timesheet_and_working_hours_for_employees('2021-12-01', '2021-12-31')
        self.assertEqual(working_hours[employee.id]['units_to_work'], 23, "Number of days should be 184h / 8h per day = 23d")

        company.timesheet_encode_uom_id = self.env.ref('uom.product_uom_hour').id

        # Create a user in the second company and link it to the employee created above
        user = self.env['res.users'].with_company(company).create({
            'name': 'Juste Leblanc',
            'login': 'juste_leblanc',
            'group_ids': [
                Command.link(self.env.ref('project.group_project_user').id),
                Command.link(self.env.ref('hr_timesheet.group_hr_timesheet_user').id),
            ],
            'company_ids': [Command.link(company.id), Command.link(self.project_customer.company_id.id),],
        })
        employee.user_id = user

        # Create a timesheet for a project in the first company for the employee in the second company
        self.assertTrue(employee.company_id != self.project_customer.company_id)
        self.assertTrue(user.company_id != self.project_customer.company_id)
        Timesheet = self.env['account.analytic.line']
        Timesheet.with_user(user).create({
            'project_id': self.project_customer.id,
            'task_id': self.task1.id,
            'unit_amount': 1.0,
        })

        # Read the timesheets and working hours of the second company employee as a manager from the first company
        # Invalidate the env cache first, because the above employee creation filled the fields data as superuser.
        # The data of the fields must be emptied so the manager user fetches the data again.
        self.env.invalidate_all()
        # Simulate the manager seeing the timesheet in task form view.
        employee_with_company_manager = employee.with_context(allowed_company_ids=self.user_manager.company_id.ids)
        working_hours = employee_with_company_manager.with_user(
            self.user_manager
        ).get_timesheet_and_working_hours_for_employees('2021-04-01', '2021-04-30')
        self.assertEqual(working_hours[employee.id]['worked_hours'], 1.0)

        # Now, same thing but archiving the employee. The manager should still be able to read his timesheet
        # despite the fact the employee has been archived.
        employee.active = False
        self.env.invalidate_all()
        working_hours = employee_with_company_manager.with_user(
            self.user_manager
        ).get_timesheet_and_working_hours_for_employees('2021-04-01', '2021-04-30')
        self.assertEqual(working_hours[employee.id]['worked_hours'], 1.0)

        # Now same thing but with the multi-company employee rule disabled
        # Users are allowed to disable multi-company rules at will,
        # the code should be compliant with that,
        # and should still work/not crash when the multi-company rule is disabled
        self.env.ref('hr.hr_employee_comp_rule').active = False
        self.env.invalidate_all()
        working_hours = employee_with_company_manager.with_user(
            self.user_manager
        ).get_timesheet_and_working_hours_for_employees('2021-04-01', '2021-04-30')
        self.assertEqual(working_hours[employee.id]['worked_hours'], 1.0)

    def test_timesheet_reminder(self):
        """ Reminder mail will be sent to both manager Administrator and User Officer to validate the timesheet """
        date = datetime(2022, 3, 2, 8, 8, 15)

        user = self.env.ref('base.user_admin')
        self.user_employee.company_id.timesheet_mail_nextdate = date
        self.user_employee.employee_id.timesheet_manager_id = self.user_manager.id

        with freeze_time(date), self.mock_mail_gateway():
            self.env['res.company']._cron_timesheet_reminder()
            self.assertEqual(
                len(self._new_mails.filtered(lambda x: x.res_id == user.employee_id.id)), 0,
                "No email should be sent to the 'Administrator Manager' since he has no timesheet to validate")
            self.assertEqual(
                len(self._new_mails.filtered(lambda x: x.res_id == self.empl_manager.id)), 0,
                "No email should be sent to the 'User Empl Officer' since he has no timesheet to validate")

            self.user_employee.company_id.timesheet_mail_nextdate = date
            Timesheet = self.env['account.analytic.line']
            timesheet_vals = {
                'name': "my timesheet",
                'project_id': self.project_customer.id,
                'task_id': self.task1.id,
                'date': datetime(2022, 2, 25, 8, 8, 15),
                'unit_amount': 8.0,
            }
            Timesheet.with_user(self.user_employee).create({**timesheet_vals})
            self.env['res.company']._cron_timesheet_reminder()
            mails = self._new_mails.filtered(lambda x: x.res_id == self.empl_manager.id)
            self.assertEqual(
                len(mails), 1,
                "An email should be sent to the 'User Empl Officer' since he has a timesheet to validate")
            # Check that the action contained within the template
            action = self.env.ref(re.search(r"action-([a-zA-Z_\.]+)\?", mails.body_html).group(1), raise_if_not_found=True)
            self.assertEqual(action, self.env.ref('timesheet_grid.timesheet_grid_to_validate_action'))

    def test_timesheet_employee_reminder(self):
        """ Reminder mail will be sent to each Users' Employee """

        date = datetime(2022, 3, 3, 8, 8, 15)

        Timesheet = self.env['account.analytic.line']
        timesheet_vals = {
            'name': "my timesheet",
            'project_id': self.project_customer.id,
            'date': datetime(2022, 3, 2, 8, 8, 15),
            'unit_amount': 8.0,
        }
        Timesheet.with_user(self.user_employee).create({**timesheet_vals, 'task_id': self.task2.id})
        Timesheet.with_user(self.user_employee2).create({**timesheet_vals, 'task_id': self.task1.id})

        self.user_employee.company_id.timesheet_mail_employee_nextdate = date

        with freeze_time(date), self.mock_mail_gateway():
            self.env['res.company']._cron_timesheet_reminder_employee()
            self.assertEqual(len(self._new_mails.filtered(lambda x: x.res_id == self.empl_employee.id)), 1, "An email sent to the 'User Empl Employee'")
            self.assertEqual(len(self._new_mails.filtered(lambda x: x.res_id == self.empl_employee2.id)), 1, "An email sent to the 'User Empl Employee 2'")

    def test_grid_update_cell(self):
        """ Test updating timesheet grid cells.

            - A user can update cells belonging to tasks assigned to them,
              even if they're part of private projects.
            - A user cannot update their own timesheets after validation.
            - Updating validated timesheets as timesheet manager should create
              additional timesheets instead of modifying existing ones.
        """
        Timesheet = self.env['account.analytic.line']
        self.empl_employee.timesheet_manager_id = self.user_manager
        self.project_customer.privacy_visibility = 'followers'
        self.task1.user_ids += self.user_employee

        self.assertNotIn(self.user_employee.partner_id, self.project_customer.message_follower_ids.partner_id,
                         "Employee shouldn't have to follow a project to update a timesheetable task")
        Timesheet.with_user(self.user_employee).grid_update_cell([('id', '=', self.timesheet1.id)], 'unit_amount', 2.0)

        sheet_count = Timesheet.search_count([('employee_id', '=', self.empl_employee.id)])
        self.timesheet1.with_user(self.user_manager).action_validate_timesheet()

        # employee cannot update cell after validation
        with self.assertRaises(AccessError):
            Timesheet.with_user(self.user_employee).grid_update_cell([('id', '=', self.timesheet1.id)], 'unit_amount', 2.0)
        Timesheet.with_user(self.user_manager).grid_update_cell([('id', '=', self.timesheet1.id)], 'unit_amount', 2.0)

        self.assertEqual(Timesheet.search_count([('employee_id', '=', self.empl_employee.id)]), sheet_count + 1,
                         "Should create new timesheet instead of updating validated timesheet in cell")

    def test_grid_update_cell_uses_default_name_from_context(self):
        """ grid_update_cell should use the description from context (default_name)
            so the new timesheet stays in the same group as the original one.
        """
        Timesheet = self.env['account.analytic.line']
        description = "Development work"
        today = fields.Date.today()

        timesheet = Timesheet.with_user(self.user_manager).create({
            'name': description,
            'project_id': self.project_customer.id,
            'task_id': self.task1.id,
            'employee_id': self.empl_manager.id,
            'unit_amount': 2.0,
        })
        timesheet.with_user(self.user_manager).action_validate_timesheet()

        Timesheet.with_user(self.user_manager).with_context(
            default_name=description,
        ).grid_update_cell([('id', '=', timesheet.id)], 'unit_amount', 1.0)

        new_timesheet = Timesheet.search([
            ('employee_id', '=', self.empl_manager.id),
            ('date', '=', today),
            ('id', '!=', timesheet.id),
        ])
        self.assertEqual(len(new_timesheet), 1)
        self.assertEqual(
            new_timesheet.name, description,
            "New timesheet should use the description from context, not '/'",
        )

    EMPTY_CELL_DOMAIN = [('id', 'in', [])]

    def test_grid_update_cell_without_project(self):
        """ When the grid row holds too little data to create a timesheet, the user is
            redirected to the form view instead of getting a plain error.
        """
        Timesheet = self.env['account.analytic.line']
        with self.assertRaises(RedirectWarning) as catcher:
            Timesheet.with_user(self.user_employee).grid_update_cell(
                self.EMPTY_CELL_DOMAIN, 'unit_amount', 3.0,
            )
        action = catcher.exception.args[1]
        self.assertEqual(action['res_model'], 'account.analytic.line')
        self.assertEqual(
            action['context']['default_unit_amount'], 3.0,
            "The time entered in the cell should be prefilled in the form view")

    def test_grid_update_cell_with_task_only(self):
        """ The project of the task of the row is used when the row itself has no project. """
        Timesheet = self.env['account.analytic.line']
        Timesheet.with_user(self.user_manager).with_context(
            default_task_id=self.task1.id,
        ).grid_update_cell(self.EMPTY_CELL_DOMAIN, 'unit_amount', 3.0)

        timesheet = Timesheet.search([('task_id', '=', self.task1.id), ('unit_amount', '=', 3.0)])
        self.assertEqual(len(timesheet), 1)
        self.assertEqual(timesheet.project_id, self.task1.project_id)

    def test_grid_update_cell_on_project_without_timesheets(self):
        """ No timesheet can be created on a project which does not allow timesheets. """
        project = self.env['project.project'].create({
            'name': 'Project without timesheets',
            'allow_timesheets': False,
        })
        with self.assertRaises(UserError):
            self.env['account.analytic.line'].with_user(self.user_manager).with_context(
                default_project_id=project.id,
            ).grid_update_cell(self.EMPTY_CELL_DOMAIN, 'unit_amount', 3.0)

    def test_get_daily_working_hours(self):
        """
        Check number of daily working hours for different timezones.
        """
        employee = self.user_employee.employee_id
        employee.resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'Employee calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 0.5, 'hour_to': 4.5}),
                (0, 0, {'dayofweek': '1', 'hour_from': 0.5, 'hour_to': 2.5}),
                (0, 0, {'dayofweek': '1', 'hour_from': 21.5, 'hour_to': 23.5}),
                (0, 0, {'dayofweek': '4', 'hour_from': 19.5, 'hour_to': 23.5}),
            ]
        })
        self.user_employee.tz = 'Etc/GMT+12'
        working_hours_gmt_plus_12 = self.user_employee.with_user(self.user_employee).get_daily_working_hours('2021-03-22', '2021-03-26')

        self.user_employee.tz = 'Etc/GMT-12'
        working_hours_gmt_minus_12 = self.user_employee.with_user(self.user_employee).get_daily_working_hours('2021-03-22', '2021-03-26')

        expected_hours = {
            '2021-03-22': 4.0,
            '2021-03-23': 4.0,
            '2021-03-24': 0,
            '2021-03-25': 0,
            '2021-03-26': 4.0,
        }
        self.assertEqual(working_hours_gmt_plus_12, expected_hours)
        self.assertEqual(working_hours_gmt_minus_12, expected_hours)

        # test that we get correct daily hours with flexible schedules
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 10,
            'hours_per_day': 2,
        })
        employee.resource_calendar_id = flexible_calendar

        flexible_expected_hours = {
            '2021-03-22': 2.0,
            '2021-03-23': 2.0,
            '2021-03-24': 2.0,
            '2021-03-25': 2.0,
            '2021-03-26': 2.0,
            'full_time_required_hours': 7.14,
        }
        flexible_daily_hours = self.user_employee.with_user(self.user_employee).get_daily_working_hours('2021-03-22', '2021-03-26')
        self.assertEqual(flexible_expected_hours, flexible_daily_hours)

    def test_validation_timesheet_at_current_date(self):
        Timesheet = self.env['account.analytic.line']
        timesheet1, timesheet2 = Timesheet.create([
            {
                'name': '/',
                'project_id': self.project_customer.id,
                'employee_id': self.empl_employee.id,
                'unit_amount': 1.0,
            } for i in range(2)
        ])
        timesheet1.with_user(self.user_manager).action_validate_timesheet()
        self.assertTrue(timesheet1.validated)

        self.assertEqual(
            self.empl_employee.last_validated_timesheet_date,
            date.today(),
            'The last validated timesheet date set on the employee should be the current one.'
        )

        timesheet = Timesheet.with_user(self.user_employee).create({
            'name': '/',
            'project_id': self.project_customer.id,
            'unit_amount': 2.0,
        })
        self.assertEqual(timesheet.employee_id, self.empl_employee)

        timesheet2.with_user(self.user_manager).action_validate_timesheet()
        self.assertTrue(timesheet2.validated)

        with self.assertRaises(AccessError):
            Timesheet.with_user(self.user_employee).create({
                'name': '/',
                'project_id': self.project_customer.id,
                'unit_amount': 1.0,
                'date': date.today() - relativedelta(days=1),
            })

    def test_timesheet_entry_with_multiple_projects(self):
        Timesheet = self.env['account.analytic.line']

        # Create project
        project_customer2 = self.env['project.project'].create({
            'name': 'Project Y',
            'allow_timesheets': True,
            'partner_id': self.partner.id,
            'account_id': self.analytic_account.id,
        })

        # Create two timesheet entries for the same employee, one for each project, with different unit amounts
        Timesheet.create([
            {
                'name': 'Timesheet 1',
                'project_id': self.project_customer.id,
                'employee_id': self.empl_employee.id,
                'unit_amount': 5.0,
                'date': '2024-01-02',
            },
            {
                'name': 'Timesheet 2',
                'project_id': project_customer2.id,
                'employee_id': self.empl_employee.id,
                'unit_amount': 10.0,
                'date': '2024-01-02',
            },
        ])

        timesheet_count = Timesheet.search_count([('employee_id', '=', self.empl_employee.id), ('date', '=', '2024-01-02')])
        Timesheet.grid_update_cell([('employee_id', '=', self.empl_employee.id), ('date', '=', '2024-01-02')], 'unit_amount', 3.0)
        self.assertEqual(
            Timesheet.search_count([('employee_id', '=', self.empl_employee.id), ('date', '=', '2024-01-02')]),
            timesheet_count + 1,
            "Grid update cell should create new timesheet if cell contains multiple timesheets"
        )

        # Disable timesheet feature for projects
        self.project_customer.allow_timesheets = False
        project_customer2.allow_timesheets = False

        # Raise user error if timesheet is disabled in both projects
        with self.assertRaises(UserError):
            Timesheet.grid_update_cell([('employee_id', '=', self.empl_employee.id), ('date', '=', '2024-01-02')], 'unit_amount', 5.0)

    def test_timesheet_task_consistency_when_project_change(self):
        """
            Test that the change of `project` of a task results in:
            - non-validated timesheets have the new project associated.
            - validated timesheets do not get change and keep the initial project.
        """
        task = self.timesheet1.task_id
        initial_project = self.timesheet1.project_id

        # create a valid timesheet and non-validated timesheet under the same task
        self.timesheet1.with_user(self.user_manager).action_validate_timesheet()
        timesheet_valid = self.timesheet1
        timesheet_non_valid = self.env['account.analytic.line'].with_user(self.user_manager).create({
            'name': "non valid timesheet",
            'project_id': initial_project.id,
            'task_id': task.id,
            'unit_amount': 2.0,
        })

        # create a new project with timesheet feature
        new_project = self.env['project.project'].create([{'name': 'Project 2', 'allow_timesheets': True}])

        # change the project of the task
        form = Form(task.with_user(self.env.user))
        form.project_id = new_project
        form.save()
        self.assertEqual(timesheet_valid.project_id, initial_project,
                         "Validated timesheet should keep the same project when the task's project is changed.")
        self.assertEqual(timesheet_non_valid.project_id, new_project,
                         "Non-validated timesheet should have the new project set when the task's project is changed.")

    def test_timesheet_check_warning_when_project_change(self):
        """
            1)  Test that when a task changes its project, if the task contains at least one non-validated timesheet AND
                the new project has no timesheet feature available, a warning notification should be raised.
            2)  The project of the task should be changed even if a warning is raised.
            3)  Second part checks that no warning is raised when the timesheets are validated.
        """

        # (1) create project without timesheet feature
        non_tracked_project = self.env['project.project'].create({
            'name': 'Project without timesheet',
            'allow_timesheets': False,
            'partner_id': self.partner.id,
        })

        # first task including non-validated timesheet
        task_1 = self.timesheet1.task_id

        # change the project of the task containing non-validated timesheet, to the project without timesheet feature
        task_1.with_user(self.env.user).write({'project_id': non_tracked_project.id})
        warning = task_1._onchange_project_id()
        self.assertTrue(warning, "Warning message should be returned")

        # (2) verify that after the warning, the project_id is changed and its non-validated timesheets gets the new project
        self.assertEqual(task_1.project_id, non_tracked_project,
                         "The task's project should be changed even if the warning is raised.")

        # (3) second task including only validated timesheet
        task_2 = self.timesheet2.task_id
        self.timesheet2.with_user(self.user_manager).action_validate_timesheet()

        # change the project of the task only containing validated timesheet, to the project without timesheet feature
        task_2.with_user(self.env.user).write({'project_id': non_tracked_project.id})
        warning = task_2._onchange_project_id()
        self.assertFalse(warning, "No warning should be raised when the task's timesheets are validated.")
