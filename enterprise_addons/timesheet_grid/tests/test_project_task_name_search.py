# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_timesheet.tests.test_timesheet import TestCommonTimesheet


class TestProjectTaskNameSearch(TestCommonTimesheet):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.task3 = cls.env['project.task'].create({
            'name': 'Task Three',
            'project_id': cls.project_customer.id,
        })

        cls.user_no_employee = cls.env['res.users'].create({
            'name': 'User No Employee',
            'login': 'user_no_employee',
            'email': 'noemployee@test.com',
            'group_ids': [(6, 0, [cls.env.ref('hr_timesheet.group_hr_timesheet_user').id])],
        })

        cls.env['account.analytic.line'].create([
            {
                'name': 'Timesheet Task 1',
                'project_id': cls.project_customer.id,
                'task_id': cls.task1.id,
                'employee_id': cls.empl_employee.id,
                'unit_amount': 1.0,
            },
            {
                'name': 'Timesheet Task 2',
                'project_id': cls.project_customer.id,
                'task_id': cls.task2.id,
                'employee_id': cls.empl_employee.id,
                'unit_amount': 1.0,
            },
        ])

    def _name_search(self, user, name='', domain=None, limit=100, timer_context=True):
        """Convenience wrapper that calls name_search with the right context."""
        ctx = {'timesheet_timer_search': True} if timer_context else {}
        domain = domain or [('project_id', '=', self.project_customer.id)]
        return self.env['project.task'].with_user(user).with_context(**ctx).name_search(
            name=name, domain=domain, limit=limit,
        )

    def test_name_search_with_name_falls_back_to_standard(self):
        """Providing a non-empty name disables the recent-first logic."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, name='Task One')]
        # Standard ilike search: only task1 ('Task One') matches.
        self.assertIn(self.task1.id, result_ids)
        self.assertNotIn(self.task2.id, result_ids)
        self.assertNotIn(self.task3.id, result_ids)

    def test_name_search_without_context_flag_falls_back_to_standard(self):
        """Omitting timesheet_timer_search in context disables the recent-first logic."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, timer_context=False)]
        # Standard search returns all project_customer tasks.
        self.assertIn(self.task1.id, result_ids)
        self.assertIn(self.task2.id, result_ids)
        self.assertIn(self.task3.id, result_ids)

    def test_name_search_without_employee_falls_back_to_standard(self):
        """A user with no employee record falls back to the standard name_search."""
        result_ids = [r[0] for r in self._name_search(self.user_no_employee)]
        self.assertIn(self.task1.id, result_ids)
        self.assertIn(self.task2.id, result_ids)
        self.assertIn(self.task3.id, result_ids)

    def test_name_search_no_recent_timesheets_falls_back_to_standard(self):
        """An employee with no timesheets on tasks falls back to the standard name_search."""
        # user_employee2 / empl_employee2 has no timesheets on any task in project_customer.
        result_ids = [r[0] for r in self._name_search(self.user_employee2)]
        self.assertIn(self.task1.id, result_ids)
        self.assertIn(self.task2.id, result_ids)
        self.assertIn(self.task3.id, result_ids)

    # ------------------------------------------------------------------
    # Recent-first cases
    # ------------------------------------------------------------------

    def test_name_search_recent_tasks_appear_first(self):
        """Tasks with recent timesheets for the employee precede tasks without."""
        result_ids = [r[0] for r in self._name_search(self.user_employee)]

        self.assertIn(self.task1.id, result_ids)
        self.assertIn(self.task2.id, result_ids)
        self.assertIn(self.task3.id, result_ids)

        idx_task3 = result_ids.index(self.task3.id)
        self.assertLess(
            result_ids.index(self.task1.id), idx_task3,
            "task1 (has recent timesheets) should appear before task3 (no timesheets)",
        )
        self.assertLess(
            result_ids.index(self.task2.id), idx_task3,
            "task2 (has recent timesheets) should appear before task3 (no timesheets)",
        )

    def test_name_search_skips_standard_search_when_limit_reached(self):
        """When the recent-task count meets the limit, the standard search is skipped."""
        result_ids = [r[0] for r in self._name_search(self.user_employee, limit=2)]

        self.assertIn(self.task1.id, result_ids)
        self.assertIn(self.task2.id, result_ids)
        self.assertNotIn(self.task3.id, result_ids)
