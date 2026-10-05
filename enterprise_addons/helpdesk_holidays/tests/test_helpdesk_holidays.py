# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta
from freezegun import freeze_time

from odoo import Command

from odoo.addons.helpdesk.tests.common import HelpdeskCommon
from odoo.tests import tagged

from odoo.addons.hr_holidays.tests.common import TestHrHolidaysCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHelpdeskHolidays(HelpdeskCommon, TestHrHolidaysCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Legal Leaves',
            'code': 'Legal Leaves',
            'count_as': 'absence',
            'requires_allocation': False,
            'unit_of_measure': 'day',
        })

        cls.user_hruser.group_ids |= cls.env.ref('helpdesk.group_helpdesk_user')
        cls.user_hrmanager.group_ids |= cls.env.ref('helpdesk.group_helpdesk_manager')
        cls.user_employee.group_ids |= cls.env.ref('helpdesk.group_helpdesk_user')

        cls.company_2 = cls.env['res.company'].create({
            'name': 'Company 2',
        })
        cls.employee_emp.company_id = cls.company_2

        cls.test_team.write({
            'auto_assignment': True,
            'assign_method': 'randomly',
            'member_ids': [
                Command.set([
                    cls.user_hruser_id,
                    cls.user_hrmanager_id,
                    cls.user_employee_id,
                ]),
            ],
        })

    def new_ticket(self, vals=None):
        if vals is None:
            vals = {}
        return self.env['helpdesk.ticket'].create({
            'name': 'Ticket',
            'team_id': self.test_team.id,
        } | vals)

    def test_random_assignment_employee_time_off(self):
        leave = self.env['hr.leave'].create({
            'employee_id': self.employee_hruser.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date.today(),
            'request_date_to': date.today() + timedelta(days=6),
        })
        leave.action_approve()

        self.assertEqual(self.new_ticket().user_id, self.user_hrmanager, "The created ticket should be automatically assigned to hrmanager")
        self.assertEqual(self.new_ticket().user_id, self.user_employee, "The created ticket should be automatically assigned to employee")
        self.assertEqual(self.new_ticket().user_id, self.user_hrmanager, "The created ticket should be automatically assigned to hrmanager")

    def test_random_assignment_employee_time_off_without_access(self):
        leave = self.env['hr.leave'].create({
            'employee_id': self.employee_hruser.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date.today(),
            'request_date_to': date.today() + timedelta(days=6),
        })
        leave.action_approve()

        ticket = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'Ticket',
            'team_id': self.test_team.id,
        })
        self.assertEqual(ticket.user_id, self.user_hrmanager, "The ticket created by a user without access to time off should be automatically assigned to hrmanager")

    def test_balanced_assignment_employee_time_off(self):
        self.test_team.assign_method = 'balanced'

        self.env['helpdesk.ticket'].create([{
            'name': f"Ticket {i}",
            'team_id': self.test_team.id,
            'stage_id': stage_id.id,
            'user_id': user_id.id,
        } for i, (stage_id, user_id) in enumerate((
            (self.stage_new, self.user_hrmanager),
            (self.stage_new, self.user_employee),
            (self.stage_progress, self.user_employee),
        ))])

        leave = self.env['hr.leave'].create({
            'employee_id': self.employee_hrmanager.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date.today(),
            'request_date_to': date.today() + timedelta(days=6),
        })
        leave.action_approve()

        self.assertEqual(self.new_ticket().user_id, self.user_hruser, "The created ticket should be automatically assigned to hruser")
        self.assertEqual(self.new_ticket().user_id, self.user_hruser, "The created ticket should be automatically assigned to hruser")
        self.assertEqual(self.new_ticket().user_id, self.user_hruser, "The created ticket should be automatically assigned to hruser")

    def test_tags_assignment_employee_time_off(self):
        self.test_team.assign_method = 'tags'

        tag = self.env['helpdesk.tag'].create({
            'name': "Test tag",
        })
        self.env['helpdesk.tag.assignment'].create({
            'team_id': self.test_team.id,
            'tag_id': tag.id,
            'user_ids': [Command.link(user_id) for user_id in [self.user_hrmanager.id, self.user_hruser.id]],
        })

        leave = self.env['hr.leave'].create({
            'employee_id': self.employee_hruser.id,
            'work_entry_type_id': self.work_entry_type.id,
            'request_date_from': date.today(),
            'request_date_to': date.today() + timedelta(days=6),
        })
        leave.action_approve()

        vals = {
            'tag_ids': [Command.link(tag.id)],
        }

        # We can't test for sure that new tickets will always be assigned to hrmanager since it's random, but this should be good enough.
        self.assertEqual(self.new_ticket(vals).user_id, self.user_hrmanager, "The created ticket should be automatically assigned to hrmanager")
        self.assertEqual(self.new_ticket(vals).user_id, self.user_hrmanager, "The created ticket should be automatically assigned to hrmanager")

    def test_assignment_global_leave(self):
        self.env['resource.calendar.leaves'].create({
            'date_from': datetime.now().strftime('%Y-%m-%d 00:00:00'),
            'date_to': (datetime.now() + timedelta(days=6)).strftime('%Y-%m-%d 23:59:59'),
        })

        self.assertEqual(self.new_ticket().user_id, self.user_employee, "The created ticket should be automatically assigned to employee")
        self.assertEqual(self.new_ticket().user_id, self.user_employee, "The created ticket should be automatically assigned to employee")
        self.assertEqual(self.new_ticket().user_id, self.user_employee, "The created ticket should be automatically assigned to employee")

    # Freeze the time a Monday, so that it's outside the working schedule
    @freeze_time('2022-03-14')
    def test_assignment_resource_calendar(self):
        self.employee_hruser.resource_id.calendar_id = self.env['resource.calendar'].create({
            'name': 'Half Week',
            'hours_per_day': 8.0,
            'attendance_ids': [
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 17})
            ]
        })

        self.assertEqual(self.new_ticket().user_id, self.user_hrmanager, "The created ticket should be automatically assigned to hrmanager")
        self.assertEqual(self.new_ticket().user_id, self.user_employee, "The created ticket should be automatically assigned to employee")
        self.assertEqual(self.new_ticket().user_id, self.user_hrmanager, "The created ticket should be automatically assigned to hrmanager")
