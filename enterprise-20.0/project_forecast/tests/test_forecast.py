# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged, freeze_time, Form
from odoo.exceptions import UserError
from .common import TestCommonForecast


@freeze_time('2019-01-01')
@tagged('-at_install', 'post_install')
class TestForecastCreationAndEditing(TestCommonForecast):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.classPatch(cls.env.cr, 'now', fields.Datetime.now)
        with freeze_time('2019-01-01'):
            cls.setUpEmployees()
            cls.setUpProjects()

        # planning_shift on one day (planning mode)
        cls.slot = cls.env['planning.slot'].create({
            'project_id': cls.project_opera.id,
            'resource_ids': cls.employee_bert.resource_id.ids,
            'start_datetime': datetime(2019, 6, 6, 8, 0, 0),  # 6/6/2019 is a tuesday, so a working day
            'end_datetime': datetime(2019, 6, 6, 17, 0, 0),
        })

    def test_creating_a_planning_shift_allocated_hours_are_correct(self):
        self.assertEqual(self.slot.allocated_hours, 8.0, 'resource hours should be a full workday')

        self.slot.write({'allocated_percentage': 50})
        self.assertEqual(self.slot.allocated_hours, 4.0, 'resource hours should be a half duration')

        # self.slot on non working days
        values = {
            'allocated_percentage': 100,
            'start_datetime': datetime(2019, 6, 2, 8, 0, 0),  # sunday morning
            'end_datetime': datetime(2019, 6, 2, 17, 0, 0)  # sunday evening, same sunday, so employee is not working
        }
        self.slot.write(values)

        self.assertEqual(self.slot.allocated_hours, 0, 'resource hours should be a full day working hours')

        # self.slot on multiple days (forecast mode)
        values = {
            'allocated_percentage': 100,   # full week
            'start_datetime': datetime(2019, 6, 3, 0, 0, 0),  # 6/3/2019 is a monday
            'end_datetime': datetime(2019, 6, 8, 23, 59, 0)  # 6/8/2019 is a sunday, so we have a full week
        }
        self.slot.write(values)

        self.assertEqual(self.slot.allocated_hours, 40, 'resource hours should be a full week\'s available hours')

    def test_creating_a_planning_shift_with_flexible_hours_allocated_hours_are_correct(self):
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
            'hours_per_week': 40,
            'hours_per_day': 8,
        })
        self.employee_bert.resource_id.write({
            'calendar_id': flexible_calendar.id,
        })
        self.assertEqual(self.slot.allocated_hours, 8.0, 'resource hours should be a full workday')

        self.slot.write({'allocated_percentage': 50})
        self.assertEqual(self.slot.allocated_hours, 4.0, 'resource hours should be a half duration')

        # self.slot on non working days
        values = {
            'allocated_percentage': 100,
            'start_datetime': datetime(2019, 6, 2, 8, 0, 0),  # sunday morning
            'end_datetime': datetime(2019, 6, 2, 17, 0, 0)  # sunday evening, same sunday, so employee is not working
        }
        self.slot.write(values)

        self.assertEqual(self.slot.allocated_hours, 8, 'resource hours should be a full day working hours')

        # self.slot on multiple days (forecast mode)
        values = {
            'allocated_percentage': 100,   # full week
            'start_datetime': datetime(2019, 6, 3, 0, 0, 0),  # 6/3/2019 is a monday
            'end_datetime': datetime(2019, 6, 8, 23, 0, 0)  # 6/8/2019 is a sunday, so we have a full week
        }
        self.slot.write(values)
        self.assertEqual(self.slot.allocated_hours, 40, 'flexible resources have a week rate limit defined in the contract, 40 hours in this case')

    @freeze_time("2023-11-20")
    def test_shift_creation_from_project(self):
        self.env.user.tz = 'Asia/Kolkata'
        PlanningTemplate = self.env['planning.slot.template']
        Project = self.env['project.project']

        project_a = Project.create({'name': 'project_a'})
        project_b = Project.create({'name': 'project_b'})

        template_a, template_b, template_none = PlanningTemplate.create([
            {
                'start_time': 8,
                'end_time': 10,
                'duration_days': 1,
                'project_id': project_a.id,
            },
            {
                'start_time': 8,
                'end_time': 12,
                'duration_days': 1,
                'project_id': project_b.id,
            },
            {
                'start_time': 8,
                'end_time': 10,
                'duration_days': 1,
            },
        ])
        self.assertEqual(template_a.duration_days, 1, "Duration in days should be a 1 day according to resource calendar.")
        self.assertEqual(template_a.end_time, 10.0, "End time should be 2 hours from start hours.")

        slot = self.env['planning.slot'].create({'template_id': template_a.id})
        self.assertEqual(slot.project_id.id, slot.template_autocomplete_ids.mapped('project_id').id, "Project of the slot and shift template should be same.")
        self.assertIn(template_a.id, slot.template_autocomplete_ids.ids, "Template with the same project should be suggested.")
        self.assertNotIn(template_b.id, slot.template_autocomplete_ids.ids, "Template with another project should not be suggested.")
        self.assertIn(template_none.id, slot.template_autocomplete_ids.ids, "Template with no project should be suggested.")

        slot.template_id = template_b.id
        self.assertEqual(slot.project_id.id, slot.template_autocomplete_ids.mapped('project_id').id, "Project of the slot and shift template should be same.")
        self.assertNotIn(template_a.id, slot.template_autocomplete_ids.ids, "Template with another project should not be suggested.")
        self.assertIn(template_b.id, slot.template_autocomplete_ids.ids, "Template with the same project should be suggested.")
        self.assertIn(template_none.id, slot.template_autocomplete_ids.ids, "Template with no project should be suggested.")

    def test_consistency_change_project_company(self):
        new_company = self.env['res.company'].create({'name': 'New Company'})
        # Check that we cannot change the company of the project as it is already linked to shifts that are in another company
        with self.assertRaises(UserError):
            self.project_opera.company_id = new_company

    @freeze_time('2019-06-06')
    def test_auto_plan_closest_shift_from_same_project(self):
        project = self.env['project.project'].create({'name': 'Planning Project'})
        *dummy, slot_to_plan = self.env['planning.slot'].create([
            {
                'project_id': project.id,
                'resource_ids': self.employee_bert.resource_id.ids,
                'start_datetime': datetime(2019, 6, 3, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 3, 9, 0, 0),
            },
            {
                'project_id': project.id,
                'resource_ids': self.employee_janice.resource_id.ids,
                'start_datetime': datetime(2019, 6, 4, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 4, 9, 0, 0),
            },
            {
                'project_id': project.id,
                'resource_ids': self.employee_joseph.resource_id.ids,
                'start_datetime': datetime(2019, 6, 5, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 5, 9, 0, 0),
            },
            {
                'project_id': project.id,
                'start_datetime': datetime(2019, 6, 6, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 6, 9, 0, 0),
            },
        ])
        slot_to_plan.auto_plan_id()
        self.assertEqual(
            slot_to_plan.resource_ids,
            self.employee_joseph.resource_id,
            "The shift to plan should be linked to the resource of the closest shift (whose deadline is the closest "
            "from the current date) of the same project."
        )

    @freeze_time('2019-01-01 08:00:00')
    def test_compute_scheduled_datetime_in_task(self):
        task = self.task_opera_place_new_chairs.copy()
        self.env['planning.slot'].create([
            {'task_id': self.task_opera_place_new_chairs.id, 'start_datetime': datetime.now(), 'end_datetime': datetime.now() + relativedelta(hours=2)},
            {'task_id': self.task_opera_place_new_chairs.id, 'start_datetime': datetime.now() + relativedelta(days=2), 'end_datetime': datetime.now() + relativedelta(days=2, hours=2)},
            {'task_id': task.id, 'start_datetime': datetime.now() - relativedelta(hours=2), 'end_datetime': datetime.now() - relativedelta(hours=1)},
            {'task_id': task.id, 'start_datetime': datetime.now() - relativedelta(hours=1), 'end_datetime': datetime.now() + relativedelta(hours=1)},
            {'task_id': self.task_horizon_dawn.id, 'start_datetime': datetime.now() - relativedelta(days=2), 'end_datetime': datetime.now() + relativedelta(days=-2, hours=2)},
            {'task_id': self.task_horizon_dawn.id, 'start_datetime': datetime.now() + relativedelta(days=2), 'end_datetime': datetime.now() + relativedelta(days=2, hours=2)},
        ])
        (self.task_opera_place_new_chairs + self.task_horizon_dawn + task).invalidate_recordset(['scheduled_datetime'])
        self.assertEqual(self.task_opera_place_new_chairs.scheduled_datetime, datetime.now())
        self.assertEqual(task.scheduled_datetime, datetime.now() - relativedelta(hours=2))
        self.assertEqual(self.task_horizon_dawn.scheduled_datetime, datetime.now() + relativedelta(days=2))

    def test_slot_template_company_check_with_project_and_task(self):
        self.project_opera.company_id = self.env.company.id
        self.task_opera_place_new_chairs.company_id = self.env.company.id
        template = self.env['planning.slot.template'].create({
            'company_id': self.env.company.id,
            'project_id': self.project_opera.id,
            'task_id': self.task_opera_place_new_chairs.id,
        })
        company_2 = self.env['res.company'].create({'name': 'Company 2'})
        with Form(template) as slot_template:
            slot_template.company_id = company_2
            self.assertFalse(slot_template.project_id, 'The project should be unset when the company is changed to a company that is different from the one of the project')
            self.assertFalse(slot_template.task_id, 'The task should be unset when the company is changed to a company that is different from the one of the task')

    @freeze_time('2019-06-06')
    def test_auto_plan_with_missmatching_roles(self):
        """
        Ensures that the auto plan feature does not assign a resource
        which does not have the required role for the slot.
        """
        project = self.env['project.project'].create({'name': 'Planning Project'})
        role_a, role_b = self.env['planning.role'].create([
            {
                'name': 'Role A',
                'resource_ids': [self.employee_bert.resource_id.id]
            },
            {
                'name': 'Role B',
                'resource_ids': [self.employee_joseph.resource_id.id]
            },
        ])
        slot_bert, first_slot_joseph, second_slot_joseph, slot_no_role = self.env['planning.slot'].create([
            {
                'project_id': project.id,
                'role_id': role_a.id,
                'start_datetime': datetime(2019, 6, 3, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 3, 9, 0, 0),
            },
            {
                'project_id': project.id,
                'role_id': role_b.id,
                'start_datetime': datetime(2019, 6, 4, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 4, 9, 0, 0),
            },
            {
                'project_id': project.id,
                'role_id': role_b.id,
                'start_datetime': datetime(2019, 6, 4, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 4, 9, 0, 0),
            },
            {
                'project_id': project.id,
                'start_datetime': datetime(2019, 6, 4, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 4, 9, 0, 0),
            },
        ])
        slot_bert.auto_plan_id()
        self.assertEqual(slot_bert.resource_ids, self.employee_bert.resource_id)

        first_slot_joseph.auto_plan_id()
        self.assertEqual(first_slot_joseph.resource_ids, self.employee_joseph.resource_id)

        second_slot_joseph.auto_plan_id()
        self.assertFalse(second_slot_joseph.resource_ids, "Cannot assign anyone: Joseph is busy and Bert does not have the right role.")

        slot_no_role.auto_plan_id()
        self.assertEqual(slot_no_role.resource_ids, self.employee_bert.resource_id, "Bert should be assigned, as he worked on that project before.")

    def test_auto_plan_open_shifts_of_several_roles(self):
        """
        Ensures that the auto plan feature can be given the open shifts with different roles.
        """
        project = self.env['project.project'].create({'name': 'Planning Project'})
        role_a, role_b = self.env['planning.role'].create([
            {
                'name': 'Role A',
                'resource_ids': [self.employee_bert.resource_id.id],
            },
            {
                'name': 'Role B',
                'resource_ids': [self.employee_joseph.resource_id.id],
            },
        ])
        slot_role_a, slot_role_b = self.env['planning.slot'].create([
            {
                'project_id': project.id,
                'role_id': role.id,
                'start_datetime': datetime(2019, 6, 3, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 3, 9, 0, 0),
            }
            for role in (role_a, role_b)
        ])

        self.env['planning.slot'].with_context(
            default_start_datetime="2019-06-02 22:00:00",
            default_end_datetime="2019-06-08 22:00:00",
        ).auto_plan_ids([('id', 'in', (slot_role_a + slot_role_b).ids)])

        self.assertEqual(slot_role_a.resource_ids, self.employee_bert.resource_id)
        self.assertEqual(slot_role_b.resource_ids, self.employee_joseph.resource_id)
