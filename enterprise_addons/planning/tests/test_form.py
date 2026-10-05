# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests import tagged, Form, new_test_user
from .common import TestCommonPlanning


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPlanningForm(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.resource_calendar_38_hours_per_week = cls.env['resource.calendar'].create([{
            'name': "Test Calendar : 38 Hours/Week",
            'hours_per_day': 7.6,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }])

        cls.setUpEmployees()
        cls.employee_janice.resource_calendar_id = cls.resource_calendar_38_hours_per_week.id

        cls.test_user = new_test_user(cls.env, login='testuser', groups='planning.group_planning_manager', tz='Europe/Brussels', resource_calendar_id='resource_calendar_id')

    def test_planning_no_employee_no_company(self):
        """ test multi day slot without calendar (no employee nor company) """
        # Required for `company_id` to be visible in the view
        self.env.user.group_ids += self.env.ref('base.group_multi_company')
        with Form(self.env['planning.slot']) as slot:
            start, end = datetime(2020, 1, 1, 8, 0), datetime(2020, 1, 11, 18, 0)
            slot.start_datetime = start
            slot.end_datetime = end
            slot.resource_ids = self.env['resource.resource']
            slot.company_id = self.env['res.company']
            self.assertEqual(slot.allocated_hours, (end - start).total_seconds() / (60 * 60))
            # The test is really weird.
            # It tests the behavior of the computed field `allocated_hours` when there is no company
            # but `company_id` on `planning.slot` is required
            # The fact the test worked previously is because `Form` allowed to change fields
            # which were supposed to be invisible
            # and the checking of the `required` modifier is skipped when the field is invisible
            # The `company_id` field was invisible because the user was not part of the `base.group_multi_company` group
            # So the test was changing an invisible field, which is not supposed to be possible in the web client
            # and then the checking of the `required` modifier was skipped because the field was invisible
            # Now that the field is made visible, by adding the multi company group,
            # it checks the `required` as it should have,
            # and therefore the test failed because it set the `company_id` to False on purpose
            # while the field is required ¯\_(ツ)_/¯
            slot.company_id = self.env.company

    def planning_form(self, timezone, start, end, expected_start, expected_end):
        self.employee_janice.tz = timezone
        context = dict(
            default_resource_ids=self.employee_janice.resource_id.ids,
            default_start_datetime=start,
            default_end_datetime=end,
        )
        with Form(self.env['planning.slot'].with_user(self.test_user).with_context(context)) as slot:
            tz = ZoneInfo(self.employee_janice.tz)
            start_decimal_time = slot.start_datetime.astimezone(tz).hour + slot.start_datetime.astimezone(tz).minute / 60
            self.assertEqual(start_decimal_time, expected_start,
                             "The planning slot doesn't start at the same time than the employee's resource calendar")
            end_decimal_time = slot.end_datetime.astimezone(tz).hour + slot.end_datetime.astimezone(tz).minute / 60
            self.assertEqual(end_decimal_time, expected_end,
                             "The planning slot doesn't end at the same time than the employee's resource calendar")

    def test_planning_employee_different_timezone(self):
        # When a slot is selected on the frontend, the start and end datetime are from 00:00:00 to 23:59:59 in the user timezone
        start, end = datetime(2020, 1, 1, 23, 0, 0), datetime(2020, 1, 2, 22, 59, 59)
        self.planning_form('Asia/Kolkata', start, end, 8, 16.6)
        self.planning_form('America/Montreal', start, end, 8, 16.6)

    def test_create_material_resource_and_assign_role(self):
        """
        Verify that material resources are created and assigned roles correctly.

        Steps:
            - Create a planning role
            - Assign Officer: Manage all employees to the planning manager
            - Create a material-type resource
            - Confirm no roles are initially assigned
            - Assign a role to the resource
            - Check the assigned planning role and default role
        """
        toolkit_role = self.env['planning.role'].create({'name': 'Toolkit'})

        self.test_user.group_ids += self.env.ref('hr.group_hr_user')

        with Form(self.env['resource.resource'].with_user(self.test_user)) as resource_form:
            resource_form.name = "Material Resource"
            resource_form.resource_type = 'material'
        material_resource = resource_form.save()

        self.assertFalse(material_resource.role_ids, "Initially, no role should be assigned to the resource.")
        self.assertFalse(material_resource.default_role_id, "Initially, no default role should be assigned.")

        material_resource.role_ids = toolkit_role
        self.assertEqual(material_resource.resource_type, 'material', "The resource type should be 'material'.")
        self.assertEqual(material_resource.role_ids, toolkit_role, "The assigned planning role should match the expected role.")
        self.assertEqual(material_resource.default_role_id, toolkit_role, "The default role should match the assigned planning role.")

    @freeze_time("2025-03-30 01:00:00")
    def test_plan_shift_to_flexible_employee_and_save_template(self):
        developer_role = self.env['planning.role'].create({
            'name': 'Developer',
            'color': 2,
        })
        flexible_calendar = self.env['resource.calendar'].create({
            'name': 'Flexible Calendar',
            'calendar_type': 'undefined',
            'attendance_ids': [],
        })
        self.employee_joseph.write({
            'resource_calendar_id': flexible_calendar.id,
            'default_planning_role_id': developer_role.id,
            'tz': 'Europe/Brussels',
        })
        expected_start_datetime = datetime.now() + relativedelta(hour=8, minute=0, second=0)
        expected_end_datetime = datetime.now() + relativedelta(hour=12, minute=0, second=0)
        slot_form = Form(self.env['planning.slot'], view="planning.planning_view_form_in_gantt")
        slot_form.resource_ids = self.resource_joseph
        self.assertEqual(slot_form.role_id, developer_role)
        slot_form.start_datetime = expected_start_datetime
        slot_form.end_datetime = expected_end_datetime
        slot = slot_form.save()
        slot.action_save_template()
        self.assertTrue(slot.allocated_hours > 0)
        self.assertEqual(slot.start_datetime, expected_start_datetime)
        self.assertEqual(slot.end_datetime, expected_end_datetime)

    def test_my_planning_assigns_current_user_and_its_materials_by_default(self):
        material = self.env['resource.resource'].create({
            'name': "Material Resource",
            'resource_type': 'material',
            'assigned_employee_id': self.employee_bert.id,
        })
        self.employee_bert.user_id = self.test_user
        with Form(self.env['planning.slot'].with_user(self.employee_bert.user_id).with_context(my_planning_action=True)) as slot:
            self.assertEqual((self.resource_bert + material).ids, slot.resource_ids.ids, "The slot should include the current user and its assigned materials")
