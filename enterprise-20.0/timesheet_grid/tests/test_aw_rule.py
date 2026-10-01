from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from odoo.addons.mail.tests.common import mail_new_test_user


class TestAwRule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_a = mail_new_test_user(
            cls.env,
            name="Normal User A",
            login="user_a",
            groups="hr_timesheet.group_hr_timesheet_user"
        )
        cls.user_b = mail_new_test_user(
            cls.env,
            name="Normal User B",
            login="user_b",
            groups="hr_timesheet.group_hr_timesheet_user"
        )
        cls.admin_user = mail_new_test_user(
            cls.env,
            name="Admin User",
            login="admin_user",
            groups="hr_timesheet.group_timesheet_manager"
        )
        cls.user_a.action_create_employee()
        cls.user_b.action_create_employee()
        cls.admin_user.action_create_employee()

        cls.common_rule_values = {
            "regex": "regex",
            "template": "template",
            "type": "odoo",
        }
        cls.global_rule = cls.env["aw.rule"].with_user(cls.admin_user).create({
            "name": "Global Rule",
        } | cls.common_rule_values)

        cls.department = cls.env["hr.department"].create({"name": "R&D"})

    def test_aw_rule_check_regex(self):
        rule = self.env["aw.rule"].create({
            "name": "Test Rule",
            "template": "Test Rule",
            "type": "odoo",
            "regex": "regex",   # Valid Regex, no error
        })
        with self.assertRaises(ValidationError, msg="An invalid regex should trigger the constraint."):
            rule.regex = "(regex"

    def test_read_access(self):
        """
        Timesheet users can read global, department, and their own private rules.
        Timesheet admins can read global and department rules, and their own private rules.
        """
        self.user_a.employee_id.department_id = self.department
        self.user_b.employee_id.department_id = self.department
        department_rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Department Rule",
            "applies_to": "departments",
            "department_ids": [Command.set(self.department.ids)],
        } | self.common_rule_values)

        private_rule_b = self.env["aw.rule"].with_user(self.user_b).create({
            "name": "Private B",
        } | self.common_rule_values)

        rules_a = self.env["aw.rule"].with_user(self.user_a).search([])
        self.assertIn(self.global_rule, rules_a)
        self.assertIn(department_rule, rules_a)
        self.assertNotIn(private_rule_b, rules_a)

        rules_admin = self.env["aw.rule"].with_user(self.admin_user).search([])
        self.assertIn(self.global_rule, rules_admin)
        self.assertIn(department_rule, rules_admin)
        self.assertNotIn(private_rule_b, rules_admin)

    def test_write_unlink_access(self):
        """
        Timesheet users can modify their own private rules,
        but cannot modify or delete global or department rules.

        Timesheet admins can modify global, department,
        and their own private rules.
        """

        admin_rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Admin Rule",
        } | self.common_rule_values)

        with self.assertRaises(AccessError):
            admin_rule.with_user(self.user_a).write({"name": "Forbidden Name"})

        with self.assertRaises(AccessError):
            admin_rule.with_user(self.user_a).unlink()

        admin_rule.with_user(self.admin_user).write({"name": "Admin Edit"})
        self.assertEqual(admin_rule.name, "Admin Edit")
        self.assertEqual(admin_rule.applies_to, "everyone")

        admin_rule.with_user(self.admin_user).write({
            "applies_to": "departments",
            "department_ids": [Command.set(self.department.ids)],
        })

        self.assertEqual(admin_rule.applies_to, "departments")
        self.assertEqual(admin_rule.department_ids, self.department)

        self.user_a.employee_id.department_id = self.department
        with self.assertRaises(AccessError):
            admin_rule.with_user(self.user_a).write({"name": "user Name"})

        with self.assertRaises(AccessError):
            admin_rule.with_user(self.user_a).unlink()

        admin_rule.with_user(self.admin_user).write({
            "applies_to": "private",
        })
        self.assertEqual(admin_rule.applies_to, "private")

        admin_rule.with_user(self.admin_user).unlink()
        self.assertFalse(admin_rule.exists())

        rule_a = self.env["aw.rule"].with_user(self.user_a).create({
            "name": "Rule A",
        } | self.common_rule_values)

        rule_a.with_user(self.user_a).write({"name": "Updated A"})
        self.assertEqual(rule_a.name, "Updated A")

    def test_copy_appends_copy_suffix(self):
        rule = self.env["aw.rule"].create({
            "name": "Original Rule",
        } | self.common_rule_values)
        duplicate = rule.copy()
        self.assertEqual(duplicate.name, "Original Rule (copy)")

    def test_project_without_company_persists_when_rule_company_set(self):
        project = self.env["project.project"].create({"name": "No Company Project"})
        rule = self.env["aw.rule"].create({
            "name": "Project Rule",
            "project_id": project.id,
        } | self.common_rule_values)
        rule.company_id = self.env.company
        self.assertEqual(
            rule.project_id, project,
            "A project without a company should remain selected when a company is set on the rule.",
        )

    def test_project_with_mismatched_company_cleared(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        project = self.env["project.project"].create({
            "name": "Other Company Project",
            "company_id": other_company.id,
        })
        rule = self.env["aw.rule"].create({
            "name": "Project Rule",
            "project_id": project.id,
        } | self.common_rule_values)
        rule.company_id = self.env.company
        self.assertFalse(
            rule.project_id,
            "A project belonging to a different company than the rule should be cleared.",
        )

    def test_task_cleared_when_project_removed(self):
        project = self.env["project.project"].create({"name": "Project", "allow_timesheets": True})
        task = self.env["project.task"].create({"name": "Task", "project_id": project.id})
        rule = self.env["aw.rule"].create({
            "name": "Task Rule",
            "task_id": task.id,
        } | self.common_rule_values)
        self.assertEqual(rule.project_id, project, "Selecting a task should fill in its project.")

        form = Form(rule)
        form.project_id = self.env["project.project"]
        self.assertFalse(
            form.task_id,
            "The task should be dropped as soon as the project is removed, before saving.",
        )
        form.save()
        self.assertFalse(rule.task_id)

    def test_task_with_mismatched_company_cleared(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        project = self.env["project.project"].create({
            "name": "Other Company Project",
            "company_id": other_company.id,
        })
        task = self.env["project.task"].create({"name": "Task", "project_id": project.id})
        rule = self.env["aw.rule"].create({
            "name": "Task Rule",
            "task_id": task.id,
        } | self.common_rule_values)
        form = Form(rule)
        form.company_id = self.env.company
        self.assertFalse(
            form.task_id,
            "The task should be dropped as soon as the company is set, before saving.",
        )
        form.save()
        self.assertFalse(
            rule.task_id,
            "A task belonging to a different company than the rule should be cleared.",
        )

    def test_project_moved_to_another_company_cleared(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        project = self.env["project.project"].create({"name": "No Company Project"})
        task = self.env["project.task"].create({"name": "Task", "project_id": project.id})
        rule = self.env["aw.rule"].create({
            "name": "Project Rule",
            "company_id": self.env.company.id,
            "task_id": task.id,
        } | self.common_rule_values)
        self.assertEqual(rule.project_id, project)

        project.company_id = other_company
        self.assertFalse(
            rule.project_id,
            "A project moved to another company than the rule should be unlinked from it.",
        )
        self.assertFalse(
            rule.task_id,
            "The task of a project moved to another company should be unlinked as well.",
        )

    def test_task_moved_to_another_company_cleared(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        project = self.env["project.project"].create({"name": "No Company Project"})
        task = self.env["project.task"].create({"name": "Task", "project_id": project.id})
        rule = self.env["aw.rule"].create({
            "name": "Task Rule",
            "company_id": self.env.company.id,
            "task_id": task.id,
        } | self.common_rule_values)

        task.company_id = other_company
        self.assertFalse(
            rule.task_id,
            "A task moved to another company than the rule should be unlinked from it.",
        )

    def test_project_follows_the_task_moved_to_another_project(self):
        project = self.env["project.project"].create({"name": "Project"})
        other_project = self.env["project.project"].create({"name": "Other Project"})
        task = self.env["project.task"].create({"name": "Task", "project_id": project.id})
        rule = self.env["aw.rule"].create({
            "name": "Task Rule",
            "task_id": task.id,
        } | self.common_rule_values)
        self.assertEqual(rule.project_id, project)

        task.project_id = other_project
        self.assertEqual(
            rule.project_id, other_project,
            "The project of the rule should follow the task moved to another project.",
        )

    def test_task_moved_to_a_project_of_another_company_cleared(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        project = self.env["project.project"].create({"name": "No Company Project"})
        other_project = self.env["project.project"].create({
            "name": "Other Company Project",
            "company_id": other_company.id,
        })
        task = self.env["project.task"].create({"name": "Task", "project_id": project.id})
        rule = self.env["aw.rule"].create({
            "name": "Task Rule",
            "company_id": self.env.company.id,
            "task_id": task.id,
        } | self.common_rule_values)

        task.project_id = other_project
        self.assertFalse(
            rule.task_id,
            "A task moved to a project of another company should be unlinked from the rule.",
        )

    def test_department_moved_to_another_company_cleared(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        department = self.env["hr.department"].create({"name": "Support"})
        child_department = self.env["hr.department"].create({
            "name": "Support L2",
            "parent_id": department.id,
        })
        rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Department Rule",
            "company_id": self.env.company.id,
            "applies_to": "departments",
            "department_ids": [Command.set((department + child_department).ids)],
        } | self.common_rule_values)

        department.company_id = other_company
        self.assertFalse(
            rule.department_ids,
            "Departments moved to another company than the rule should be unlinked from it.",
        )

    def test_departments_cleared_when_rule_company_changed(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        department = self.env["hr.department"].create({
            "name": "Support",
            "company_id": self.env.company.id,
        })
        global_department = self.env["hr.department"].create({
            "name": "Global Support",
            "company_id": False,
        })
        rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Department Rule",
            "company_id": self.env.company.id,
            "applies_to": "departments",
            "department_ids": [Command.set((department + global_department).ids)],
        } | self.common_rule_values)

        rule.company_id = other_company
        self.assertEqual(
            rule.department_ids, global_department,
            "Only the departments of another company should be unlinked from the rule.",
        )

    def test_applicable_rule(self):
        self.admin_user.employee_id.department_id = self.department
        self.user_a.employee_id.department_id = self.department
        everyone_rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Everyone Rule",
        } | self.common_rule_values)

        department_rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Department Rule",
            "applies_to": "departments",
            "department_ids": [Command.set(self.department.ids)],
        } | self.common_rule_values)

        private_rule_a = self.env["aw.rule"].with_user(self.user_a).create({
            "name": "Private A",
        } | self.common_rule_values)

        private_rule_b = self.env["aw.rule"].with_user(self.user_b).create({
            "name": "Private B",
        } | self.common_rule_values)

        self.admin_user.group_ids |= self.env.ref("base.group_system")

        company_rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Company Rule",
            "company_id": self.env.company.id,
        } | self.common_rule_values)

        other_company = self.env["res.company"].create({
            "name": "Other Company",
        })
        self.admin_user.company_ids |= other_company
        other_company_rule = self.env["aw.rule"].with_user(self.admin_user).create({
            "name": "Other Company Rule",
            "company_id": other_company.id,
        } | self.common_rule_values)

        def _get_rule_names(user):
            rules = self.env["aw.rule"].with_user(user).get_applicable_rules(["name"])
            return {r["name"] for r in rules}

        rule_names = _get_rule_names(self.user_a)
        # Rules for everyone, user's department rules, and private rules of user_a should be returned
        self.assertIn(everyone_rule.name, rule_names)
        self.assertIn(department_rule.name, rule_names)
        self.assertIn(private_rule_a.name, rule_names)
        self.assertIn(company_rule.name, rule_names)

        # Private rule of other user should not be returned
        self.assertNotIn(private_rule_b.name, rule_names)
        # Only rules belonging to the current company should be returned. other company rules should not be included
        self.assertNotIn(other_company_rule.name, rule_names)

        department_1 = self.env["hr.department"].create({"name": "Test Department"})
        department_rule.write({
            "department_ids": [Command.set([department_1.id])]
        })
        rule_names = _get_rule_names(self.user_a)
        # Rules belonging to other departments should not be returned
        self.assertNotIn(department_rule, rule_names)

    def test_side_activity_from_type(self):
        self.assertFalse(self.global_rule.side_activity)
        self.global_rule.type = "messaging"
        self.assertTrue(self.global_rule.side_activity)
