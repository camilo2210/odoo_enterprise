from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo.tests import freeze_time

from odoo.addons.project.tests.test_project_base import TestProjectCommon


@freeze_time("2025-12-08 08:00:00")
class TestProjectTemplate(TestProjectCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.developer_role, cls.designer_role = cls.env['project.role'].create([
            {'name': 'Developer', 'user_ids': cls.user_projectuser.ids},
            {'name': 'Designer', 'user_ids': cls.user_projectmanager.ids},
        ])
        cls.project_template = cls.env['project.project'].create({
            'name': 'Project template',
            'is_template': True,
        })
        common_task_vals = {'is_template': True, 'project_id': cls.project_template.id}
        cls.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cls.task_template_1, cls.task_template_2, cls.task_template_3 = cls.env['project.task'].create([
            {
                **common_task_vals,
                'name': 'Task Template 1',
                'role_ids': cls.developer_role.ids,
                'planned_date_begin': cls.today,
                'date_deadline': cls.today + relativedelta(hour=17, days=7),
            },
            {
                **common_task_vals,
                'name': 'Task Template 2',
                'role_ids': cls.designer_role.ids,
                'planned_date_begin': cls.today,
                'date_deadline': cls.today + relativedelta(hour=17, days=7),
            },
            {
                **common_task_vals,
                'name': 'Task Template 3',
                'role_ids': (cls.developer_role + cls.designer_role).ids,
                'planned_date_begin': cls.today,
                'date_deadline': cls.today + relativedelta(hour=17, days=7),
            },
        ])

    def test_create_project_base_on_template_with_role(self):
        self.task_1.write({
            'planned_date_begin': self.today,
            'date_deadline': self.today + relativedelta(hour=17, days=7),
        })
        project = self.project_template.action_create_from_template({
            'name': 'Project',
            'date_start': self.today.date(),
            'date': (self.today + relativedelta(days=15)).date(),
        })
        self.assertFalse(project.task_ids.filtered(lambda t: t.name == 'Task Template 1').user_ids)
        self.assertEqual(project.task_ids.filtered(lambda t: t.name == 'Task Template 2').user_ids, self.user_projectmanager)
        self.assertEqual(project.task_ids.filtered(lambda t: t.name == 'Task Template 3').user_ids, self.user_projectmanager)

    def test_scheduling_no_assignees(self):
        """
        When creating a project from a template with planned dates, if the template has concurrent unassigned tasks,
        the created project should be able to, too.
        """
        project_template = self.env['project.project'].create({
            'name': 'Project Template',
            'date_start': date(2025, 11, 3),
            'date': date(2025, 11, 21),
        })
        self.env['project.task'].create([
            {
                'name': 'Task 1',
                'is_template': True,
                'project_id': project_template.id,
                'planned_date_begin': datetime(2025, 11, 3, 7),
                'date_deadline': datetime(2025, 11, 5, 16),
                'allocated_hours': 24,
            },
            {
                'name': 'Task 2',
                'is_template': True,
                'project_id': project_template.id,
                'planned_date_begin': datetime(2025, 11, 3, 7),
                'date_deadline': datetime(2025, 11, 11, 16),
                'allocated_hours': 56,
            },
            {
                'name': 'Task 3',
                'is_template': True,
                'project_id': project_template.id,
                'planned_date_begin': datetime(2025, 11, 5, 7),
                'date_deadline': datetime(2025, 11, 6, 16),
                'allocated_hours': 16,
            },
        ])

        project = project_template.action_create_from_template({
            'name': 'Project',
            'date_start': date(2025, 12, 15),
            'date': date(2025, 12, 31),
        })
        expected_dates = [
            (datetime(2025, 12, 15, 7), datetime(2025, 12, 17, 15)),
            (datetime(2025, 12, 15, 7), datetime(2025, 12, 23, 15)),
            (datetime(2025, 12, 17, 7), datetime(2025, 12, 18, 15)),
        ]
        for task, (start, end) in zip(project.task_ids.sorted('name'), expected_dates):
            self.assertEqual(task.planned_date_begin, start)
            self.assertEqual(task.date_deadline, end)
