# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .common import TestHelpdeskTimesheetCommon


class TestHelpdeskTicketNameSearch(TestHelpdeskTimesheetCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ticket_recent, cls.ticket_no_timesheets = cls.env['helpdesk.ticket'].create([
            {'name': 'Recent Ticket', 'team_id': cls.helpdesk_team.id},
            {'name': 'Other Ticket', 'team_id': cls.helpdesk_team.id}
        ])

        cls.user_no_employee = cls.env['res.users'].create({
            'name': 'User No Employee (helpdesk)',
            'login': 'user_no_employee_helpdesk',
            'email': 'noemployee_helpdesk@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('hr_timesheet.group_hr_timesheet_user').id,
                cls.env.ref('helpdesk.group_helpdesk_user').id,
            ])],
        })

        cls.env['account.analytic.line'].create({
            'name': 'Timesheet on Recent Ticket',
            'project_id': cls.project.id,
            'helpdesk_ticket_id': cls.ticket_recent.id,
            'employee_id': cls.empl_employee.id,
            'unit_amount': 1.0,
        })

    def _name_search(self, user, name='', domain=None, limit=100, timer_context=True):
        """Convenience wrapper that calls name_search with the right context."""
        ctx = {'timesheet_timer_search': True} if timer_context else {}
        domain = domain or [('id', 'in', [self.ticket_recent.id, self.ticket_no_timesheets.id])]
        return self.env['helpdesk.ticket'].with_user(user).with_context(**ctx).name_search(
            name=name, domain=domain, limit=limit,
        )

    def test_name_search_with_name_falls_back_to_standard(self):
        """Providing a non-empty name disables the recent-first logic."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, name='Recent')]
        self.assertIn(self.ticket_recent.id, result_ids)
        self.assertNotIn(self.ticket_no_timesheets.id, result_ids)

    def test_name_search_without_context_flag_falls_back_to_standard(self):
        """Omitting timesheet_timer_search in context disables the recent-first logic."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, timer_context=False)]
        self.assertIn(self.ticket_recent.id, result_ids)
        self.assertIn(self.ticket_no_timesheets.id, result_ids)

    def test_name_search_without_employee_falls_back_to_standard(self):
        """A user with no employee record falls back to the standard name_search."""
        result_ids = [r[0] for r in self._name_search(self.user_no_employee)]
        self.assertIn(self.ticket_recent.id, result_ids)
        self.assertIn(self.ticket_no_timesheets.id, result_ids)

    def test_name_search_no_recent_timesheets_falls_back_to_standard(self):
        """An employee with no timesheets on any ticket falls back to the standard name_search."""
        result_ids = [r[0] for r in self._name_search(self.user_employee)]
        self.assertIn(self.ticket_recent.id, result_ids)
        self.assertIn(self.ticket_no_timesheets.id, result_ids)

    def test_name_search_recent_tickets_appear_first(self):
        """Tickets with recent timesheets for the employee precede tickets without."""
        result_ids = [r[0] for r in self._name_search(self.user_employee)]

        self.assertIn(self.ticket_recent.id, result_ids)
        self.assertIn(self.ticket_no_timesheets.id, result_ids)

        self.assertLess(
            result_ids.index(self.ticket_recent.id),
            result_ids.index(self.ticket_no_timesheets.id),
            "ticket_recent (has recent timesheets) should appear before ticket_no_timesheets",
        )

    def test_name_search_skips_standard_search_when_limit_reached(self):
        """When the recent-ticket count meets the limit, the standard search is skipped."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, limit=1)]

        self.assertIn(self.ticket_recent.id, result_ids)
        self.assertNotIn(self.ticket_no_timesheets.id, result_ids)
