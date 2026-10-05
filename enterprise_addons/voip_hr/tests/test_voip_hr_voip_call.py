from odoo.fields import Command
from odoo.tests import Form
from odoo.tests.common import tagged, TransactionCase, new_test_user


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestVoipHrVoipCall(TransactionCase):
    def test_disconnected_forwarding_prefers_mobile_phone(self):
        user = new_test_user(
            self.env,
            login="mobile_forwarding_user",
            phone="+3281234567",
            country_id=self.env.ref("base.be").id,
        )
        self.env["hr.employee"].create({
            "name": "Mobile Forwarding User",
            "user_id": user.id,
            "mobile_phone": "+32499123456",
        })

        settings = user._prepare_pbx_user_settings()

        self.assertEqual(settings.voip_disconnected_outcall_number, "+32499123456")

    def test_disconnected_forwarding_falls_back_to_phone(self):
        user = new_test_user(
            self.env,
            login="phone_forwarding_user",
            phone="+3281234567",
            country_id=self.env.ref("base.be").id,
        )
        self.env["hr.employee"].create({
            "name": "Phone Forwarding User",
            "user_id": user.id,
            "mobile_phone": "invalid",
        })

        settings = user._prepare_pbx_user_settings()

        self.assertEqual(settings.voip_disconnected_outcall_number, "+3281234567")

    def test_action_log_call_with_mismatched_record_hr(self):
        """When the employee's partner differs from the call's partner, the
        domain check fails and the wizard falls back to the call's contact."""
        call_partner = self.env["res.partner"].create({"name": "Call Partner"})
        other_partner = self.env["res.partner"].create({"name": "Other Partner"})
        other_employee = self.env["hr.employee"].create({"name": "Other Employee"})
        other_partner.employee_ids = [Command.set([other_employee.id])]
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": call_partner.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="hr.employee", active_id=other_employee.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, call_partner)
            self.assertEqual(form.res_ids, f"[{call_partner.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_action_log_call_with_matching_model_hr(self):
        """When active_model=hr.employee matches a registered option (hr.employee),
        the wizard should pre-select that record type and record."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        employee = self.env["hr.employee"].create({
            "name": "Test Employee",
        })
        partner.employee_ids = [Command.set([employee.id])]
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": partner.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="hr.employee", active_id=employee.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "hr.employee")
            self.assertEqual(form.employee_id, employee)
            self.assertEqual(form.res_ids, f"[{employee.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "hr.employee")

    def test_is_within_same_company_true_same_company_employees(self):
        company = self.env["res.company"].create({"name": "Company"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company.id, partner_id=caller_partner.id)
        self.env["hr.employee"].create(
            {"name": "Caller Employee", "user_id": caller.id, "company_id": company.id},
        )
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_employee = self.env["hr.employee"].create({"name": "Callee Employee", "company_id": company.id})
        callee_partner.employee_ids = [Command.set([callee_employee.id])]
        call = self.env["voip.call"].create(
            {
                "phone_number": "+1234567890",
                "partner_id": callee_partner.id,
                "user_id": caller.id,
            },
        )

        self.assertTrue(call.is_within_same_company)

    def test_is_within_same_company_false_different_company_employees(self):
        company_1 = self.env["res.company"].create({"name": "Company 1"})
        company_2 = self.env["res.company"].create({"name": "Company 2"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company_1.id, partner_id=caller_partner.id)
        self.env["hr.employee"].create({"name": "Caller Employee", "user_id": caller.id, "company_id": company_1.id})
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_employee = self.env["hr.employee"].create({"name": "Callee Employee", "company_id": company_2.id})
        callee_partner.employee_ids = [Command.set([callee_employee.id])]
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )

        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_multiple_employees_per_user(self):
        company_1 = self.env["res.company"].create({"name": "Company 1"})
        company_2 = self.env["res.company"].create({"name": "Company 2"})
        company_3 = self.env["res.company"].create({"name": "Company 3"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company_1.id, partner_id=caller_partner.id)
        caller.company_ids = [Command.set([company_1.id, company_2.id, company_3.id])]
        self.env["hr.employee"].create({"name": "Caller Employee 1", "user_id": caller.id, "company_id": company_1.id})
        self.env["hr.employee"].create({"name": "Caller Employee 2", "user_id": caller.id, "company_id": company_2.id})
        callee_1_partner = self.env["res.partner"].create({"name": "Callee 1", "email": "callee@example.com"})
        callee_1_employee = self.env["hr.employee"].create({"name": "Callee 1 Employee", "company_id": company_1.id})
        callee_1_partner.employee_ids = [Command.set([callee_1_employee.id])]
        callee_2_partner = self.env["res.partner"].create({"name": "Callee 2", "email": "callee2@example.com"})
        callee_2_employee = self.env["hr.employee"].create({"name": "Callee 2 Employee", "company_id": company_2.id})
        callee_2_partner.employee_ids = [Command.set([callee_2_employee.id])]
        callee_3_partner = self.env["res.partner"].create({"name": "Callee 3", "email": "callee3@example.com"})
        callee_3_employee = self.env["hr.employee"].create({"name": "Callee 3 Employee", "company_id": company_3.id})
        callee_3_partner.employee_ids = [Command.set([callee_3_employee.id])]

        call_with_callee_1 = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_1_partner.id, "user_id": caller.id},
        )
        call_with_callee_2 = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_2_partner.id, "user_id": caller.id},
        )
        call_with_callee_3 = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_3_partner.id, "user_id": caller.id},
        )
        self.assertTrue(call_with_callee_1.is_within_same_company)
        self.assertTrue(call_with_callee_2.is_within_same_company)
        self.assertFalse(call_with_callee_3.is_within_same_company)

    def test_is_within_same_company_false_partner_no_employees(self):
        company = self.env["res.company"].create({"name": "Company"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company.id, partner_id=caller_partner.id)
        self.env["hr.employee"].create({"name": "Caller Employee", "user_id": caller.id, "company_id": company.id})
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_false_user_no_employees(self):
        company = self.env["res.company"].create({"name": "Company"})
        caller_partner = self.env["res.partner"].create({"name": "Caller", "email": "caller@example.com"})
        caller = new_test_user(self.env, login="user", company_id=company.id, partner_id=caller_partner.id)
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_employee = self.env["hr.employee"].create({"name": "Callee Employee", "company_id": company.id})
        callee_partner.employee_ids = [Command.set([callee_employee.id])]
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )
        self.assertFalse(call.is_within_same_company)

    def test_is_within_same_company_falls_back_to_base_logic(self):
        company_partner = self.env["res.partner"].create({"name": "Test Company"})
        caller = new_test_user(self.env, login="user")
        caller.partner_id.commercial_partner_id = company_partner
        callee_partner = self.env["res.partner"].create({"name": "Callee", "email": "callee@example.com"})
        callee_partner.commercial_partner_id = company_partner
        call = self.env["voip.call"].create(
            {"phone_number": "+1234567890", "partner_id": callee_partner.id, "user_id": caller.id},
        )
        self.assertTrue(call.is_within_same_company)
