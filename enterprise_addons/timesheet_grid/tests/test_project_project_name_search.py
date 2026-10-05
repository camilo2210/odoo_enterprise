# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet


class TestProjectProjectNameSearch(TestCommonTimesheet):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.project_recent, cls.project_no_timesheets = cls.env['project.project'].create([
            {'name': 'Recent Project', 'allow_timesheets': True},
            {'name': 'Other Project', 'allow_timesheets': True},
        ])
        cls.user_no_employee = cls.env['res.users'].create({
            'name': 'User No Employee (project)',
            'login': 'user_no_employee_project',
            'email': 'noemployee_project@test.com',
            'group_ids': [(6, 0, [cls.env.ref('hr_timesheet.group_hr_timesheet_user').id])],
        })

        cls.env['account.analytic.line'].create({
            'name': 'Timesheet on Recent Project',
            'project_id': cls.project_recent.id,
            'employee_id': cls.empl_employee.id,
            'unit_amount': 1.0,
        })

    def _name_search(self, user, name='', domain=None, limit=100, timer_context=True):
        """Convenience wrapper that calls name_search with the right context."""
        ctx = {'timesheet_timer_search': True} if timer_context else {}
        domain = domain or [('id', 'in', [self.project_recent.id, self.project_no_timesheets.id])]
        return self.env['project.project'].with_user(user).with_context(**ctx).name_search(
            name=name, domain=domain, limit=limit,
        )

    def test_name_search_with_name_falls_back_to_standard(self):
        """Providing a non-empty name disables the recent-first logic."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, name='Recent')]
        self.assertIn(self.project_recent.id, result_ids)
        self.assertNotIn(self.project_no_timesheets.id, result_ids)

    def test_name_search_without_context_flag_falls_back_to_standard(self):
        """Omitting timesheet_timer_search in context disables the recent-first logic."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, timer_context=False)]
        self.assertIn(self.project_recent.id, result_ids)
        self.assertIn(self.project_no_timesheets.id, result_ids)

    def test_name_search_without_employee_falls_back_to_standard(self):
        """A user with no employee record falls back to the standard name_search."""
        result_ids = [r[0] for r in self._name_search(self.user_no_employee)]
        self.assertIn(self.project_recent.id, result_ids)
        self.assertIn(self.project_no_timesheets.id, result_ids)

    def test_name_search_no_recent_timesheets_falls_back_to_standard(self):
        """An employee with no timesheets on any project falls back to the standard name_search."""
        result_ids = [r[0] for r in self._name_search(self.user_employee2)]
        self.assertIn(self.project_recent.id, result_ids)
        self.assertIn(self.project_no_timesheets.id, result_ids)

    def test_name_search_recent_projects_appear_first(self):
        """Projects with recent timesheets for the employee precede projects without."""
        result_ids = [r[0] for r in self._name_search(self.user_employee)]

        self.assertIn(self.project_recent.id, result_ids)
        self.assertIn(self.project_no_timesheets.id, result_ids)

        self.assertLess(
            result_ids.index(self.project_recent.id),
            result_ids.index(self.project_no_timesheets.id),
            "project_recent (has recent timesheets) should appear before project_no_timesheets",
        )

    def test_name_search_skips_standard_search_when_limit_reached(self):
        """When the recent-project count meets the limit, the standard search is skipped."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, limit=1)]

        self.assertIn(self.project_recent.id, result_ids)
        self.assertNotIn(self.project_no_timesheets.id, result_ids)

    def test_name_search_archived_project(self):
        """Archived projects should not be returned in recent projects."""
        self.project_recent.action_archive()
        result_ids = [r[0] for r in self._name_search(self.user_employee)]
        self.assertNotIn(self.project_recent.id, result_ids)
