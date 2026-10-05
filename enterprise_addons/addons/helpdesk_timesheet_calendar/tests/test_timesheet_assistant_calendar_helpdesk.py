# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.tests import tagged

from odoo.addons.helpdesk_timesheet.tests.common import TestHelpdeskTimesheetCommon


@tagged('at_install', '-post_install')
class TestTimesheetAssistantCalendarHelpdesk(TestHelpdeskTimesheetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["hr.employee"].create({
            "name": cls.env.user.name,
            "user_id": cls.env.user.id,
        })

        cls.project_team_1 = cls.env['project.project'].create({
            'name': 'Project Team 1',
            'allow_timesheets': True,
        })
        cls.project_team_2 = cls.env['project.project'].create({
            'name': 'Project Team 2',
            'allow_timesheets': True,
        })

        cls.team_with_project_1, cls.team_with_project_2, cls.team_without_project = cls.env['helpdesk.team'].create([
            {
                'name': 'Team With Project 1',
                'use_helpdesk_timesheet': True,
                'project_id': cls.project_team_1.id,
            },
            {
                'name': 'Team With Project 2',
                'use_helpdesk_timesheet': True,
                'project_id': cls.project_team_2.id,
            },
            {
                'name': 'Team Without Project',
            },
        ])

        cls.ticket_1a, cls.ticket_1b, cls.ticket_2, cls.ticket_no_project = cls.env['helpdesk.ticket'].create([
            {'name': 'Ticket 1A', 'team_id': cls.team_with_project_1.id},
            {'name': 'Ticket 1B', 'team_id': cls.team_with_project_1.id},
            {'name': 'Ticket 2', 'team_id': cls.team_with_project_2.id},
            {'name': 'Ticket No Project', 'team_id': cls.team_without_project.id},
        ])

        res_model_ticket_id = cls.env['ir.model']._get_id('helpdesk.ticket')

        cls.meeting_1a, cls.meeting_1b, cls.meeting_2, cls.meeting_no_project = cls.env['calendar.event'].create([
            {
                'name': 'Meeting Ticket 1A',
                'start': datetime(2026, 1, 13, 9, 0),
                'stop': datetime(2026, 1, 13, 10, 0),
                'res_model_id': res_model_ticket_id,
                'res_id': cls.ticket_1a.id,
            },
            {
                'name': 'Meeting Ticket 1B',
                'start': datetime(2026, 1, 13, 10, 0),
                'stop': datetime(2026, 1, 13, 11, 0),
                'res_model_id': res_model_ticket_id,
                'res_id': cls.ticket_1b.id,
            },
            {
                'name': 'Meeting Ticket 2',
                'start': datetime(2026, 1, 13, 11, 0),
                'stop': datetime(2026, 1, 13, 12, 0),
                'res_model_id': res_model_ticket_id,
                'res_id': cls.ticket_2.id,
            },
            {
                'name': 'Meeting Ticket No Project',
                'start': datetime(2026, 1, 13, 13, 0),
                'stop': datetime(2026, 1, 13, 14, 0),
                'res_model_id': res_model_ticket_id,
                'res_id': cls.ticket_no_project.id,
            },
        ])

    def test_calendar_events_resolve_helpdesk_ticket_project(self):
        events = self.env["account.analytic.line"].get_assistant_events("2026-01-13")

        meeting_1a = next(e for e in events if e["name"] == "Meeting Ticket 1A")
        self.assertEqual(meeting_1a["_res_model"], "project.project")
        self.assertEqual(meeting_1a["_res_id"], self.project_team_1.id)

        meeting_1b = next(e for e in events if e["name"] == "Meeting Ticket 1B")
        self.assertEqual(meeting_1b["_res_model"], "project.project")
        self.assertEqual(meeting_1b["_res_id"], self.project_team_1.id)

        meeting_2 = next(e for e in events if e["name"] == "Meeting Ticket 2")
        self.assertEqual(meeting_2["_res_model"], "project.project")
        self.assertEqual(meeting_2["_res_id"], self.project_team_2.id)

        meeting_no_project = next(e for e in events if e["name"] == "Meeting Ticket No Project")
        self.assertNotIn("_res_model", meeting_no_project)
        self.assertNotIn("_res_id", meeting_no_project)
