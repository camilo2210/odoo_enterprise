from datetime import datetime
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests import tagged

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet
from odoo import Command


@tagged('at_install', '-post_install')
class TestTimesheetAssistantCalendar(TestCommonTimesheet):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["hr.employee"].create({
            "name": cls.env.user.name,
            "user_id": cls.env.user.id,
        })

        cls.getters = cls.env['account.analytic.line'].with_user(cls.user_employee)._get_assistant_events_getters()

        cls.colleague_user = cls.env['res.users'].create({
                'name': 'Colleague Organizer',
                'login': 'colleague_organizer',
        })

        date_start = datetime(2026, 5, 22, 14, 0)

        cls.event_organized_by_employee = cls.env['calendar.event'].with_user(cls.user_employee).create({
            'name': 'Organized by Employee',
            'start': date_start,
            'stop': date_start + relativedelta(hours=1),
        })

        cls.event_employee_attending, cls.event_employee_declined = cls.env['calendar.event'].with_user(cls.colleague_user).create([{
                'name': 'Employee Invited',
                'start': date_start,
                'stop': date_start + relativedelta(hours=1),
                'partner_ids': [(4, cls.user_employee.partner_id.id), (4, cls.colleague_user.partner_id.id)]
            },
            {
                'name': 'Employee Declined',
                'start': date_start,
                'stop': date_start + relativedelta(hours=1),
                'partner_ids': [(4, cls.user_employee.partner_id.id), (4, cls.colleague_user.partner_id.id)]
            }
        ])

        employee_attendee = cls.env['calendar.attendee'].search([
            ('event_id', '=', cls.event_employee_declined.id),
            ('partner_id', '=', cls.user_employee.partner_id.id)
        ])
        employee_attendee.write({'state': 'declined'})

        cls.event_available = cls.env['calendar.event'].with_user(cls.colleague_user).create([{
            'name': 'Available Event',
            'start': date_start,
            'stop': date_start + relativedelta(hours=1),
            'show_as': 'free',
        }])

    def _get_events(self, day):
        calendar_getter = next(g['getter'] for g in self.getters if g['getter'].__name__ == 'get_calendar_events')
        return calendar_getter(datetime(2026, 5, day, 0, 0), datetime(2026, 5, day + 1, 0, 0))

    def test_calendar_suggestions(self):
        suggested_events = self._get_events(22)
        suggested_event_ids = [e['id'] for e in suggested_events]

        self.assertIn(
            self.event_organized_by_employee.id,
            suggested_event_ids,
            "Should fetch events organized by the user."
        )
        self.assertIn(
            self.event_employee_attending.id,
            suggested_event_ids,
            "Should fetch events where the user is an active attendee."
        )
        self.assertNotIn(
            self.event_employee_declined.id,
            suggested_event_ids,
            "Should NOT fetch events that the user explicitly declined."
        )
        self.assertNotIn(
            self.event_available.id,
            suggested_event_ids,
            "Should NOT fetch available/free events"
        )

    @freeze_time('2026-05-25 14:00:00')
    def test_timesheet_assistant_calendar_events(self):
        """
        This test ensure that the calendar events hours used in the suggestion for the timesheet assistant take into
        account the employee schedule.
        """

        _all_day_event, morning_event, _evening_event = self.env["calendar.event"].create([{
            "name": "Team meeting",
            "user_id": self.user_employee.id,
            "start": datetime(2026, 5, 18, 8, 0),
            "stop": datetime(2026, 5, 24, 18, 0),
            "show_as": "busy",
        }, {
            "name": "For the Waaagh!",
            "user_id": self.user_employee.id,
            "start": datetime(2026, 5, 25, 8, 0),
            "stop": datetime(2026, 5, 25, 10, 0),
            "show_as": "busy",
        }, {
            "name": "For the Alliance!",
            "user_id": self.user_employee.id,
            "start": datetime(2026, 5, 25, 16, 0),
            "stop": datetime(2026, 5, 25, 18, 0),
            "show_as": "busy",
        }])

        # Update the working schedule so that the employee is only supposed to work 4 hours on Wednesday.
        attendances = self.empl_employee.resource_calendar_id.attendance_ids
        self.empl_employee.resource_calendar_id.attendance_ids = attendances - attendances[5]

        # the employee use a fixed schedule
        # working day (Wednesday)
        self.assertEqual(self._get_events(20)[0]['max_hours'], 4.0)

        # working day (Friday)
        self.assertEqual(self._get_events(22)[0]['max_hours'], 8.0)

        # non-working day (sunday)
        self.assertFalse(self._get_events(24))

        # the employee use semi-flexible hours
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 70,
            'hours_per_day': 10,
        })
        self.empl_employee.resource_calendar_id = flexible_calendar
        self.assertEqual(self._get_events(22)[0]['max_hours'], 10.0)

        # the employee use flexible hours
        flexible_calendar.hours_per_week = 0
        self.assertEqual(self._get_events(24)[0]['max_hours'], 24.0)

        # The employee had a meeting in the morning. The meeting in the evening should not be fetched.
        self.assertEqual(self._get_events(25)[0]['id'], morning_event.id)

    def test_calendar_event_resolution(self):
        """
        Test all resolution scenarios for calendar events:
        - If the event is linked to a project.task directly, it resolves to that task.
        - If the event is linked to a project.project directly, it resolves to that project.
        - If the most recent timesheet among the invited partners has a task, it resolves to that task.
        - If the most recent timesheet has only a project, it resolves to that project.
        - Timesheets logged by any partner in an invited partner's tree
          (parent_id/child_ids hierarchy) are taken into account, not just
          the exact invited partner.
        - If no timesheet exists anywhere in the tree, it falls back to the most
          recently created (highest ID) task linked to a partner in the tree.
        - Failing that, it falls back to the most recently created project linked
          to a partner in the tree.
        - If nothing at all is found, no resolution is proposed.
        """
        partner_a, partner_b, partner_c, partner_c_child, partner_d, partner_e, partner_f, partner_f_child = self.env["res.partner"].create([
            {"name": "Partner A"},
            {"name": "Partner B"},
            {"name": "Partner C"},
            {"name": "Partner C Child"},
            {"name": "Partner D"},
            {"name": "Partner E"},
            {"name": "Partner F"},
            {"name": "Partner F Child"},
        ])

        partner_c_child.parent_id = partner_c
        partner_f_child.parent_id = partner_f

        project_a, project_b, project_c_child, _, project_d2, project_f = self.env["project.project"].create([
            {
                "name": "Project A",
                "partner_id": partner_a.id,
                "allow_timesheets": True,
            },
            {
                "name": "Project B",
                "partner_id": partner_b.id,
                "allow_timesheets": True,
            },
            {
                "name": "Project C Child",
                "partner_id": partner_c_child.id,
                "allow_timesheets": True,
            },
            {
                "name": "Project D1",
                "partner_id": partner_d.id,
                "allow_timesheets": True,
            },
            {
                "name": "Project D2",
                "partner_id": partner_d.id,
                "allow_timesheets": True,
            },
            {
                "name": "Project F",
                "allow_timesheets": True,
            },
        ])

        task_a = self.env["project.task"].create({
            "name": "A Specific Task",
            "project_id": project_a.id,
        })
        task_f = self.env["project.task"].create({
            "name": "F Child Task",
            "project_id": project_f.id,
            "partner_id": partner_f_child.id,
        })

        self.env["account.analytic.line"].create([
            {
                "name": "Timesheet 1",
                "date": "2026-01-01",
                "project_id": project_a.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
            {
                "name": "Timesheet 2",
                "date": "2026-01-10",
                "project_id": project_b.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
            {
                "name": "Timesheet 3",
                "date": "2026-01-12",
                "project_id": project_a.id,
                "task_id": task_a.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
            {
                "name": "Timesheet 4",
                "date": "2026-01-11",
                "project_id": project_c_child.id,
                "user_id": self.env.user.id,
                "unit_amount": 1.0,
            },
        ])

        self.env["calendar.event"].create([
            {
                "name": "Meeting 1",
                "start": datetime(2026, 1, 13, 9, 0),
                "stop": datetime(2026, 1, 13, 10, 0),
                "partner_ids": [Command.link(partner_b.id), Command.link(partner_a.id)],
            },
            {
                "name": "Meeting 2",
                "start": datetime(2026, 1, 13, 10, 0),
                "stop": datetime(2026, 1, 13, 11, 0),
                "partner_ids": [Command.link(partner_b.id)],
            },
            {
                "name": "Meeting 3",
                "start": datetime(2026, 1, 13, 14, 0),
                "stop": datetime(2026, 1, 13, 15, 0),
                "partner_ids": [Command.link(partner_c.id)],
            },
            {
                "name": "Meeting 4 - Direct Project Link",
                "start": datetime(2026, 1, 13, 11, 0),
                "stop": datetime(2026, 1, 13, 12, 0),
                "res_model_id": self.env['ir.model']._get_id('project.project'),
                "res_id": project_a.id,
            },
            {
                "name": "Meeting 5 - Direct Task Link",
                "start": datetime(2026, 1, 13, 13, 0),
                "stop": datetime(2026, 1, 13, 14, 0),
                "res_model_id": self.env['ir.model']._get_id('project.task'),
                "res_id": task_a.id,
            },
            {
                "name": "Meeting 6",
                "start": datetime(2026, 1, 13, 15, 0),
                "stop": datetime(2026, 1, 13, 16, 0),
                "partner_ids": [Command.link(partner_d.id)],
            },
            {
                "name": "Meeting 7",
                "start": datetime(2026, 1, 13, 16, 0),
                "stop": datetime(2026, 1, 13, 17, 0),
                "partner_ids": [Command.link(partner_e.id)],
            },
            {
                "name": "Meeting 8",
                "start": datetime(2026, 1, 13, 17, 0),
                "stop": datetime(2026, 1, 13, 18, 0),
                "partner_ids": [Command.link(partner_f.id)],
            },
        ])

        events = self.env["account.analytic.line"].get_assistant_events("2026-01-13")

        meeting1 = next(e for e in events if e["name"] == "Meeting 1")
        self.assertEqual(meeting1["_res_model"], "project.task")
        self.assertEqual(meeting1["_res_id"], task_a.id, "partner B and A are both invited, but partner_a has the most recent timesheet")

        meeting2 = next(e for e in events if e["name"] == "Meeting 2")
        self.assertEqual(meeting2["_res_model"], "project.project", "partner_b is not linked to any timesheet with a task")
        self.assertEqual(meeting2["_res_id"], project_b.id, "Should resolve to the specific project")

        meeting3 = next(e for e in events if e["name"] == "Meeting 3")
        self.assertEqual(meeting3["_res_model"], "project.project", "partner_c itself has no timesheet, but its child does")
        self.assertEqual(meeting3["_res_id"], project_c_child.id, "Should traverse the tree to find the timesheet logged by partner_c's child")

        meeting4 = next(e for e in events if e["name"] == "Meeting 4 - Direct Project Link")
        self.assertEqual(meeting4["_res_model"], "project.project", "The event is directly linked to a project")
        self.assertEqual(meeting4["_res_id"], project_a.id, "Should resolve directly to the linked project, no partner lookup involved")

        meeting5 = next(e for e in events if e["name"] == "Meeting 5 - Direct Task Link")
        self.assertEqual(meeting5["_res_model"], "project.task", "The event is directly linked to a task")
        self.assertEqual(meeting5["_res_id"], task_a.id, "Should resolve directly to the linked task, no partner lookup involved")

        meeting6 = next(e for e in events if e["name"] == "Meeting 6")
        self.assertEqual(meeting6["_res_model"], "project.project", "No timesheet at all for partner_d, should fall back to its linked project")
        self.assertEqual(meeting6["_res_id"], project_d2.id, "Should have picked the linked project with the highest id (most recently created)")

        meeting7 = next(e for e in events if e["name"] == "Meeting 7")
        self.assertNotIn("_res_model", meeting7, "partner_e has no timesheet and no linked project or task at all")

        meeting8 = next(e for e in events if e["name"] == "Meeting 8")
        self.assertEqual(meeting8["_res_model"], "project.task", "partner_f has no timesheet, but its child has a linked task")
        self.assertEqual(meeting8["_res_id"], task_f.id, "Should traverse the tree to find the task linked to partner_f's child")
