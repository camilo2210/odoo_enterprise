from ast import literal_eval

from odoo.tests import Form

from .common import TestVoipProjectCommon


class TestVoipCall(TestVoipProjectCommon):

    def test_action_view_tasks_uses_commercial_partner(self):
        """Smart button should show tasks from the whole partner family (commercial partner).
        New records should default to the call's partner, not the commercial partner."""
        call = self.env["voip.call"].create({
            "partner_id": self.partner_1.id,
            "phone_number": "+1234567891",
            "user_id": self.user_projectuser.id,
        })
        self.assertEqual(call.commercial_partner_task_count, self.parent_partner.task_count)
        action = call.action_view_tasks()
        tasks = self.env["project.task"].search(action["domain"])
        self.assertEqual(len(tasks), call.commercial_partner_task_count)
        self.assertEqual(action["context"]["default_partner_id"], self.partner_1.id)

    def test_action_log_call_with_mismatched_record_project(self):
        """When the task's partner is outside the call's commercial entity,
        the domain check fails and the wizard falls back to the call's contact."""
        unrelated_partner = self.env["res.partner"].create({"name": "Unrelated Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": self.partner_1.id,
        })
        task = self.env["project.task"].create({
            "name": "Task Other Partner",
            "partner_id": unrelated_partner.id,
            "project_id": self.project_pigs.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="project.task", active_id=task.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, self.partner_1)
            self.assertEqual(form.res_ids, f"[{self.partner_1.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_action_log_call_with_matching_model_project(self):
        """When active_model=project.task matches a registered option (project.task),
        the wizard should pre-select that record type and record."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": self.partner_1.id,
        })
        task = self.env["project.task"].create({
            "name": "Test Task",
            "partner_id": self.partner_1.id,
            "project_id": self.project_pigs.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="project.task", active_id=task.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "project.task")
            self.assertEqual(form.task_id, task)
            self.assertEqual(form.res_ids, f"[{task.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "project.task")

    def test_log_call_domain_covers_commercial_entity_project(self):
        """The task domain of the log activity wizard must cover tasks related
        to every partner of the call contact's commercial entity (``partner_2``
        is a sibling of ``partner_1`` in TestVoipProjectCommon)."""
        sibling_task = self.env["project.task"].create({
            "name": "Sibling Task",
            "partner_id": self.partner_2.id,
            "project_id": self.project_pigs.id,
        })
        unrelated_partner = self.env["res.partner"].create({"name": "Unrelated Partner"})
        unrelated_task = self.env["project.task"].create({
            "name": "Unrelated Task",
            "partner_id": unrelated_partner.id,
            "project_id": self.project_pigs.id,
        })
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=self.partner_1.id,
        ).new()
        tasks = self.env["project.task"].search(literal_eval(wizard.task_id_domain))
        self.assertIn(self.task_1, tasks, "own tasks stay selectable")
        self.assertIn(
            sibling_task, tasks,
            "tasks of sibling contacts of the same company become selectable",
        )
        self.assertNotIn(
            unrelated_task, tasks,
            "tasks of partners outside the commercial entity stay hidden",
        )
