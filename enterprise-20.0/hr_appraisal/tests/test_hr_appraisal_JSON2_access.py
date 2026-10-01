# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime, timedelta
from http import HTTPStatus

from odoo import Command
from odoo.tests import new_test_user, tagged
from odoo.tests.common import HttpCase
from odoo.tools import html2plaintext


@tagged("post_install")
class TestHrAppraisalJSON2Access(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Appraised Company"})

        cls.user_appraisal = new_test_user(
            cls.env,
            name="user_appraisal",
            login="user_appraisal",
            email="user_appraisal@example.com",
            groups="base.group_user,hr_appraisal.group_hr_appraisal_user",
            notification_type="email",
            company_id=cls.company.id,
        )
        cls.user_appraisal = cls.user_appraisal.with_user(cls.user_appraisal)

        cls.user_manager = new_test_user(
            cls.env,
            name="user_manager",
            login="user_manager",
            email="user_manager@example.com",
            groups="base.group_user",
            notification_type="email",
            company_id=cls.company.id,
        )
        cls.user_manager = cls.user_manager.with_user(cls.user_manager)

        cls.user_normal_employee = new_test_user(
            cls.env,
            name="user_normal_employee",
            login="user_normal_employee",
            email="user_normal_employee@example.com",
            groups="base.group_user",
            notification_type="email",
            company_id=cls.company.id,
        )
        cls.user_normal_employee = cls.user_normal_employee.with_user(cls.user_normal_employee)

        cls.employee_manager, cls.employee_normal, cls.employee_appraisal = cls.env["hr.employee"].create([
            {
                "name": "Employee Manager",
                "user_id": cls.user_manager.id,
                "company_id": cls.company.id,
            },
            {
                "name": "Employee Normal",
                "user_id": cls.user_normal_employee.id,
                "company_id": cls.company.id,
                "wage": 500,
                "contract_date_start": "2017-10-01",
                "next_appraisal_date": "2057-12-05",
            },
            {
                "name": "Employee Appraisal",
                "user_id": cls.user_appraisal.id,
                "company_id": cls.company.id,
                "wage": 500,
                "contract_date_start": "2016-12-01",
                "next_appraisal_date": "2057-12-05",
            },
        ])
        cls.env["hr.employee"].browse(cls.employee_normal.ids + cls.employee_appraisal.ids).write({
            "parent_id": cls.employee_manager.id,
        })

        cls.appraisal_normal, cls.appraisal_appraisal = cls.env["hr.appraisal"].create([
            {
                "employee_id": cls.employee_normal.id,
                "manager_ids": [Command.link(cls.employee_manager.id)],
                "note": "Only manager and appraisal users can read this",
            },
            {
                "employee_id": cls.employee_appraisal.id,
                "manager_ids": [Command.link(cls.employee_manager.id)],
                "note": "Also only manager and appraisal users can read this",
            },
        ])

        cls.assessment_note_good = cls.env["hr.appraisal.note"].create({
            "name": "Very good",
            "company_id": cls.company.id,
        })
        cls.assessment_note_bad = cls.env["hr.appraisal.note"].create({
            "name": "Very bad",
            "company_id": cls.company.id,
        })

        appraisal_key = (
            cls.user_appraisal
            .env["res.users.apikeys"]
            .sudo()
            ._generate(scope="rpc", name="test_api_access", expiration_date=datetime.now() + timedelta(days=1))
        )
        manager_key = (
            cls.user_manager
            .env["res.users.apikeys"]
            .sudo()
            ._generate(scope="rpc", name="test_api_access", expiration_date=datetime.now() + timedelta(days=1))
        )
        normal_key = (
            cls.user_normal_employee
            .env["res.users.apikeys"]
            .sudo()
            ._generate(scope="rpc", name="test_api_access", expiration_date=datetime.now() + timedelta(days=1))
        )
        cls.appraisal_bearer_header = {"Authorization": f"Bearer {appraisal_key}"}
        cls.manager_bearer_header = {"Authorization": f"Bearer {manager_key}"}
        cls.normal_bearer_header = {"Authorization": f"Bearer {normal_key}"}

    def process_response(self, response, expected_status_code):
        self.assertEqual(
            response.status_code,
            expected_status_code,
            f"Expected {expected_status_code}, got {response.status_code}: {response.text}",
        )

    def test_appraisal_flow_for_normal_user(self):
        """
        Test that a normal employee can create a draft appraisal but cannot confirm it, set a final rating, or mark it
        as done via JSON2 RPC.
        Test that an employee can write and publish their own feedback, but cannot write or publish the manager's feedback.
        Test that feedback remains hidden ('Unpublished') until published.
        """
        create_appraisal = self.url_open(
            "/json/2/hr.appraisal/create",
            json={
                "vals_list": [
                    {
                        "employee_id": self.employee_normal.id,
                        "manager_ids": [Command.link(self.employee_manager.id)],
                    },
                ],
            },
            headers=self.normal_bearer_header,
        )
        self.process_response(create_appraisal, HTTPStatus.OK)
        appraisal = self.env["hr.appraisal"].browse(create_appraisal.json())

        with self.assertLogs(level=logging.WARNING):
            employee_action_confirm = self.url_open(
                "/json/2/hr.appraisal/action_confirm",
                json={"ids": appraisal.ids},
                headers=self.normal_bearer_header,
            )
            self.process_response(employee_action_confirm, HTTPStatus.FORBIDDEN)
        self.assertEqual(appraisal.state, "1_new")

        appraisal.action_confirm()
        self.assertEqual(appraisal.state, "2_pending")

        employee_write_to_employee_feedback = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"accessible_employee_feedback": "I love this appraisal"}},
            headers=self.normal_bearer_header,
        )
        self.process_response(employee_write_to_employee_feedback, HTTPStatus.OK)

        with self.assertLogs(level=logging.WARNING):
            employee_write_to_manager_feedback = self.url_open(
                "/json/2/hr.appraisal/write",
                json={
                    "ids": appraisal.ids,
                    "vals": {"accessible_manager_feedback": "I love this normal employee"},
                },
                headers=self.normal_bearer_header,
            )
            self.process_response(employee_write_to_manager_feedback, HTTPStatus.FORBIDDEN)

        # Before publishing, manager feedback should be "Unpublished"
        appraisal.write({"accessible_manager_feedback": "Why is the employee trying to change the feedback?"})
        employee_read_manager_feedback = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": appraisal.ids, "fields": ["accessible_manager_feedback"]},
            headers=self.normal_bearer_header,
        )
        self.process_response(employee_read_manager_feedback, HTTPStatus.OK)
        self.assertEqual(
            html2plaintext(employee_read_manager_feedback.json()[0]["accessible_manager_feedback"]),
            "Unpublished",
            "Employee should not be able to read the manager feedback before it is published",
        )

        with self.assertLogs(level=logging.WARNING):
            employee_publish_manager_feedback = self.url_open(
                "/json/2/hr.appraisal/write",
                json={"ids": appraisal.ids, "vals": {"manager_feedback_published": True}},
                headers=self.normal_bearer_header,
            )
            self.process_response(employee_publish_manager_feedback, HTTPStatus.FORBIDDEN)

        # Employee can publish their own feedback
        employee_publish_employee_feedback = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"employee_feedback_published": True}},
            headers=self.normal_bearer_header,
        )
        self.process_response(employee_publish_employee_feedback, HTTPStatus.OK)

        # After publishing (by manager/sudo), manager feedback should be visible
        appraisal.write({"manager_feedback_published": True})
        employee_read_manager_feedback_published = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": appraisal.ids, "fields": ["accessible_manager_feedback"]},
            headers=self.normal_bearer_header,
        )
        self.process_response(employee_read_manager_feedback_published, HTTPStatus.OK)
        self.assertEqual(
            html2plaintext(employee_read_manager_feedback_published.json()[0]["accessible_manager_feedback"]),
            "Why is the employee trying to change the feedback?",
            "Employee should be able to read the manager feedback after it is published",
        )

        with self.assertLogs(level=logging.WARNING):
            employee_set_assessment_note = self.url_open(
                "/json/2/hr.appraisal/write",
                json={"ids": appraisal.ids, "vals": {"assessment_note": self.assessment_note_good.id}},
                headers=self.normal_bearer_header,
            )
            self.process_response(employee_set_assessment_note, HTTPStatus.FORBIDDEN)
        self.assertEqual(appraisal.assessment_note, self.env["hr.appraisal.note"])

        appraisal.assessment_note = self.assessment_note_bad.id
        self.assertEqual(appraisal.assessment_note, self.assessment_note_bad)

        with self.assertLogs(level=logging.WARNING):
            employee_action_done = self.url_open(
                "/json/2/hr.appraisal/action_done",
                json={"ids": appraisal.ids},
                headers=self.normal_bearer_header,
            )
            self.process_response(employee_action_done, HTTPStatus.FORBIDDEN)
        self.assertEqual(appraisal.state, "2_pending")

        appraisal.action_done()
        self.assertEqual(appraisal.state, "3_done")

        with self.assertLogs(level=logging.WARNING):
            employee_change_assessment_after_marking_done = self.url_open(
                "/json/2/hr.appraisal/write",
                json={
                    "ids": appraisal.ids,
                    "vals": {
                        "accessible_employee_feedback": "I actually don't like this appraisal",
                    },
                },
                headers=self.manager_bearer_header,
            )
            self.process_response(employee_change_assessment_after_marking_done, HTTPStatus.FORBIDDEN)

        with self.assertLogs(level=logging.WARNING):
            employee_action_reopen = self.url_open(
                "/json/2/hr.appraisal/action_reopen",
                json={"ids": appraisal.ids},
                headers=self.normal_bearer_header,
            )
            self.process_response(employee_action_reopen, HTTPStatus.FORBIDDEN)

    def test_appraisal_flow_for_manager_user(self):
        """
        Test that a manager can perform the full appraisal flow via JSON2 RPC for a subordinate's appraisal.
        Test that a manager can write and publish their own feedback, and can publish the employee's feedback,
        but cannot write the employee's feedback.
        Test that feedback remains hidden ('Unpublished') until published.
        """
        create_appraisal = self.url_open(
            "/json/2/hr.appraisal/create",
            json={
                "vals_list": [
                    {
                        "employee_id": self.employee_normal.id,
                        "manager_ids": [Command.link(self.employee_manager.id)],
                        "note": "This employee is good.",
                    },
                ],
            },
            headers=self.manager_bearer_header,
        )

        self.process_response(create_appraisal, HTTPStatus.OK)
        appraisal = self.env["hr.appraisal"].browse(create_appraisal.json())

        manager_action_confirm = self.url_open(
            "/json/2/hr.appraisal/action_confirm",
            json={"ids": appraisal.ids},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_action_confirm, HTTPStatus.OK)
        self.assertEqual(appraisal.state, "2_pending")

        manager_write_to_manager_feedback = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"accessible_manager_feedback": "This employee is great!"}},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_write_to_manager_feedback, HTTPStatus.OK)

        with self.assertLogs(level=logging.WARNING):
            manager_write_to_employee_feedback = self.url_open(
                "/json/2/hr.appraisal/write",
                json={
                    "ids": appraisal.ids,
                    "vals": {"accessible_employee_feedback": "My manager is great!"},
                },
                headers=self.manager_bearer_header,
            )
            self.process_response(manager_write_to_employee_feedback, HTTPStatus.FORBIDDEN)

        appraisal.write({"accessible_employee_feedback": "My manager is always trying to change my feedback. Weird."})
        manager_read_employee_feedback = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": appraisal.ids, "fields": ["accessible_employee_feedback"]},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_read_employee_feedback, HTTPStatus.OK)
        self.assertEqual(
            html2plaintext(manager_read_employee_feedback.json()[0]["accessible_employee_feedback"]),
            "Unpublished",
            "Manager should not be able to read the employee feedback before it is published",
        )

        manager_publish_employee_feedback = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"employee_feedback_published": True}},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_publish_employee_feedback, HTTPStatus.OK)

        manager_publish_manager_feedback = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"manager_feedback_published": True}},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_publish_manager_feedback, HTTPStatus.OK)

        manager_read_employee_feedback_published = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": appraisal.ids, "fields": ["accessible_employee_feedback"]},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_read_employee_feedback_published, HTTPStatus.OK)
        self.assertEqual(
            html2plaintext(manager_read_employee_feedback_published.json()[0]["accessible_employee_feedback"]),
            "My manager is always trying to change my feedback. Weird.",
            "Manager should be able to read the employee feedback after it is published",
        )

        manager_set_assessment_note = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"assessment_note": self.assessment_note_good.id}},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_set_assessment_note, HTTPStatus.OK)
        self.assertEqual(appraisal.assessment_note, self.assessment_note_good)

        manager_action_done = self.url_open(
            "/json/2/hr.appraisal/action_done",
            json={"ids": appraisal.ids},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_action_done, HTTPStatus.OK)
        self.assertEqual(appraisal.state, "3_done")

        with self.assertLogs(level=logging.WARNING):
            manager_change_note_after_marking_done = self.url_open(
                "/json/2/hr.appraisal/write",
                json={
                    "ids": appraisal.ids,
                    "vals": {
                        "assessment_note": self.assessment_note_bad.id,
                        "note": "I made a mistake, this employee is really bad",
                    },
                },
                headers=self.manager_bearer_header,
            )
            self.process_response(manager_change_note_after_marking_done, HTTPStatus.FORBIDDEN)

        manager_reopen_appraisal = self.url_open(
            "/json/2/hr.appraisal/action_reopen",
            json={"ids": appraisal.ids},
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_reopen_appraisal, HTTPStatus.OK)

        manager_change_note_after_reopen = self.url_open(
            "/json/2/hr.appraisal/write",
            json={
                "ids": appraisal.ids,
                "vals": {
                    "assessment_note": self.assessment_note_bad.id,
                    "note": "I made a mistake, this employee is really bad",
                },
            },
            headers=self.manager_bearer_header,
        )
        self.process_response(manager_change_note_after_reopen, HTTPStatus.OK)

    def test_appraisal_flow_permissions_for_appraisal_user(self):
        """
        Test that an Appraisal Officer can perform the full appraisal flow
        via JSON2 RPC for any employee's appraisal.
        """
        create_appraisal = self.url_open(
            "/json/2/hr.appraisal/create",
            json={
                "vals_list": [
                    {
                        "employee_id": self.employee_normal.id,
                        "manager_ids": [Command.link(self.employee_manager.id)],
                    },
                ],
            },
            headers=self.appraisal_bearer_header,
        )

        self.process_response(create_appraisal, HTTPStatus.OK)
        appraisal = self.env["hr.appraisal"].browse(create_appraisal.json())

        appraisal_action_confirm = self.url_open(
            "/json/2/hr.appraisal/action_confirm",
            json={"ids": appraisal.ids},
            headers=self.appraisal_bearer_header,
        )
        self.process_response(appraisal_action_confirm, HTTPStatus.OK)
        self.assertEqual(appraisal.state, "2_pending")

        appraisal_set_assessment_note = self.url_open(
            "/json/2/hr.appraisal/write",
            json={"ids": appraisal.ids, "vals": {"assessment_note": self.assessment_note_good.id}},
            headers=self.appraisal_bearer_header,
        )
        self.process_response(appraisal_set_assessment_note, HTTPStatus.OK)
        self.assertEqual(appraisal.assessment_note, self.assessment_note_good)

        appraisal_action_done = self.url_open(
            "/json/2/hr.appraisal/action_done",
            json={"ids": appraisal.ids},
            headers=self.appraisal_bearer_header,
        )
        self.process_response(appraisal_action_done, HTTPStatus.OK)
        self.assertEqual(appraisal.state, "3_done")

    def test_employee_can_not_read_private_note_via_json2(self):
        """
        Test that an employee cannot read the private 'note' field of their own appraisal via JSON2 RPC, even if they
        have read access to the record.
        """
        response = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": self.appraisal_normal.ids, "fields": ["note"]},
            headers=self.normal_bearer_header,
        )

        data = response.json()
        self.assertEqual(data[0]["note"], False, "Employee should not be able to read the private note content")

    def test_employee_can_not_read_manager_only_fields_via_json2(self):
        """
        Test that an employee cannot read the private 'note' field of their own appraisal via JSON2 RPC, even if they
        have read access to the record.
        """
        self.appraisal_normal.action_confirm()
        self.appraisal_normal.assessment_note = self.assessment_note_good
        response = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": self.appraisal_normal.ids, "fields": []},
            headers=self.normal_bearer_header,
        )

        data = response.json()
        self.assertEqual(data[0]["note"], False, "Employee should not be able to read the private note content")
        self.assertEqual(data[0]["assessment_note"], False, "Employee should not be able to read the private note content")

    def test_manager_can_read_private_note_via_json2(self):
        """
        Test that a manager can read the private 'note' field of an appraisal they are managing via JSON2 RPC.
        """
        response = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": self.appraisal_normal.ids, "fields": ["note"]},
            headers=self.manager_bearer_header,
        )

        data = response.json()
        self.assertEqual(
            html2plaintext(data[0]["note"]),
            "Only manager and appraisal users can read this",
            "Manager should be able to read the private note content of an appraisal they are managing",
        )

    def test_appraisal_users_can_read_private_note_via_json2(self):
        """
        Test that an Appraisal Officer can read the private 'note' field of any appraisal via JSON2 RPC.
        """
        response = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": self.appraisal_normal.ids, "fields": ["note"]},
            headers=self.appraisal_bearer_header,
        )

        data = response.json()
        self.assertEqual(
            html2plaintext(data[0]["note"]),
            "Only manager and appraisal users can read this",
            "Appraisal users should be able to read the private note content of other appraisals",
        )

    def test_appraisal_users_can_not_read_private_note_of_their_own_appraisal_via_json2(self):
        """
        Test that even an Appraisal Officer cannot read the private 'note' field of their own appraisal via JSON2 RPC.
        """
        response = self.url_open(
            "/json/2/hr.appraisal/read",
            json={"ids": self.appraisal_appraisal.ids, "fields": ["note"]},
            headers=self.appraisal_bearer_header,
        )

        data = response.json()
        self.assertEqual(
            data[0]["note"],
            False,
            "Appraisal users should not be able to read the private note content of their own appraisal",
        )

    def test_normal_user_can_not_create_an_appraisal_with_manager_only_fields_filled_out(self):
        """
        Test that a normal employee cannot fill restricted fields like 'note' during the creation of an appraisal
        via JSON2 RPC.
        """
        with self.assertLogs(level=logging.WARNING):
            create_appraisal = self.url_open(
                "/json/2/hr.appraisal/create",
                json={
                    "vals_list": [
                        {
                            "employee_id": self.employee_normal.id,
                            "manager_ids": [Command.link(self.employee_manager.id)],
                            "note": "This will not work",
                        },
                    ],
                },
                headers=self.normal_bearer_header,
            )

            self.process_response(create_appraisal, HTTPStatus.FORBIDDEN)

    def test_normal_user_can_not_spoof_exception_values_with_context(self):
        """
        Test that a normal employee cannot fill restricted fields like 'note' during the creation of an appraisal
        via JSON2 RPC by spoofing the exception values with a default context.
        """
        with self.assertLogs(level=logging.WARNING):
            create_appraisal = self.url_open(
                "/json/2/hr.appraisal/create",
                json={
                    "context": {
                        "default_state": "2_pending",
                        "default_note": "This will not work",
                        "default_manager_feedback_published": True,
                    },
                    "vals_list": [
                        {
                            "employee_id": self.employee_normal.id,
                            "manager_ids": [Command.link(self.employee_manager.id)],
                            "note": "This will not work",
                            "state": "2_pending",
                            "manager_feedback_published": True,
                        },
                    ],
                },
                headers=self.normal_bearer_header,
            )

            self.process_response(create_appraisal, HTTPStatus.FORBIDDEN)

    def test_normal_user_can_create_an_appraisal_with_manager_only_fields_filled_out_if_value_is_allowed(self):
        """
        Test that a normal employee can fill a restricted field (like 'state') during creation ONLY if the value
        matches one of the allowed exceptions (e.g., '1_new').
        """
        with self.assertLogs(level=logging.WARNING):
            create_approved_appraisal = self.url_open(
                "/json/2/hr.appraisal/create",
                json={
                    "vals_list": [
                        {
                            "employee_id": self.employee_normal.id,
                            "manager_ids": [Command.link(self.employee_manager.id)],
                            "state": "2_pending",
                        },
                    ],
                },
                headers=self.normal_bearer_header,
            )

            self.process_response(create_approved_appraisal, HTTPStatus.FORBIDDEN)

        create_new_appraisal = self.url_open(
            "/json/2/hr.appraisal/create",
            json={
                "vals_list": [
                    {
                        "employee_id": self.employee_normal.id,
                        "manager_ids": [Command.link(self.employee_manager.id)],
                        "state": "1_new",
                    },
                ],
            },
            headers=self.normal_bearer_header,
        )

        self.process_response(create_new_appraisal, HTTPStatus.OK)

    def test_manager_can_create_an_appraisal_with_manager_only_fields_filled_out(self):
        """
        Test that a manager can fill restricted fields (like 'note') when creating an appraisal for their subordinate
        via JSON2 RPC.
        """
        create_manager_appraisal = self.url_open(
            "/json/2/hr.appraisal/create",
            json={
                "vals_list": [
                    {
                        "employee_id": self.employee_normal.id,
                        "manager_ids": [Command.link(self.employee_manager.id)],
                        "note": "This will work",
                    },
                ],
            },
            headers=self.manager_bearer_header,
        )

        self.process_response(create_manager_appraisal, HTTPStatus.OK)
        self.assertEqual(
            self.env["hr.appraisal"].browse(create_manager_appraisal.json()).note.striptags(),
            "This will work",
            "The appraisal should contain the note 'This will work'",
        )

    def test_appraisal_user_can_create_an_appraisal_with_manager_only_fields_filled_out(self):
        """
        Test that an Appraisal Officer can fill restricted fields (like 'note') when creating any appraisal
        via JSON2 RPC.
        """
        create_appraisal_user_appraisal = self.url_open(
            "/json/2/hr.appraisal/create",
            json={
                "vals_list": [
                    {
                        "employee_id": self.employee_normal.id,
                        "manager_ids": [Command.link(self.employee_manager.id)],
                        "note": "This will work",
                    },
                ],
            },
            headers=self.appraisal_bearer_header,
        )

        self.process_response(create_appraisal_user_appraisal, HTTPStatus.OK)
        self.assertEqual(
            self.env["hr.appraisal"].browse(create_appraisal_user_appraisal.json()).note.striptags(),
            "This will work",
            "The appraisal should contain the note 'This will work'",
        )
