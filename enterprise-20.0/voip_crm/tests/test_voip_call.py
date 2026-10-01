from ast import literal_eval

from odoo.tests import Form, tagged

from .common import TestVoipCrmCommon


@tagged("post_install", "-at_install")
class TestVoipCall(TestVoipCrmCommon):

    def test_add_to_activity_queue_action(self):
        leads = self.env["crm.lead"].create([
            {"name": "Activity Queue Lead 1", "phone": "+1 202-555-0102"},
            {"name": "Activity Queue Lead 2", "phone": "+1 202-555-0103"},
        ])
        action = self.env.ref("voip_crm.action_add_to_activity_queue")

        self.assertEqual(action.model_id.model, "crm.lead")
        self.assertEqual(action.binding_model_id.model, "crm.lead")
        self.assertEqual(action.binding_view_types, "list,kanban")

        action.with_context(active_model="crm.lead", active_ids=leads.ids).run()
        # Running the action again does not create duplicate call activities
        action.with_context(active_model="crm.lead", active_ids=leads.ids).run()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", "crm.lead"),
            ("res_id", "in", leads.ids),
            ("user_id", "=", self.env.uid),
            ("activity_type_id.category", "=", "phonecall"),
        ])
        self.assertEqual(len(activities), len(leads))
        self.assertEqual(set(activities.mapped("res_id")), set(leads.ids))

    def test_action_view_opportunity_uses_commercial_partner(self):
        """Smart button should show opportunities from the whole partner family (commercial partner).
        New records should default to the call's partner, not the commercial partner."""
        parent_partner = self.env["res.partner"].create({
            "name": "Team Egypt",
            "phone": "+1233211234567",
        })
        (self.partner_no_opportunities | self.partner_one_opportunity | self.partner_multiple_opportunities).parent_id = parent_partner.id
        call = self.env["voip.call"].create({
            "partner_id": self.partner_one_opportunity.id,
            "phone_number": "+1234567891",
            "user_id": self.user_sales_salesman.id,
        })
        self.assertEqual(call.commercial_partner_opportunity_count, parent_partner.opportunity_count)
        action = call.action_view_opportunity()
        opportunities = self.env["crm.lead"].search(action["domain"])
        self.assertEqual(len(opportunities), call.commercial_partner_opportunity_count)
        self.assertEqual(action["context"]["default_partner_id"], self.partner_one_opportunity.id)

    def test_action_log_call_with_mismatched_record_crm(self):
        """When the lead's partner differs from the call's partner, the domain
        check fails and the wizard falls back to the call's contact."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": self.partner_one_opportunity.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="crm.lead", active_id=self.opportunity_2.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, self.partner_one_opportunity)
            self.assertEqual(form.res_ids, f"[{self.partner_one_opportunity.id}]")
            self.assertEqual(form.call_id, call)

    def test_action_log_call_with_matching_model_crm(self):
        """When active_model=crm.lead matches a registered option (crm.lead),
        the wizard should pre-select that record type and record."""
        call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "partner_id": self.partner_one_opportunity.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="crm.lead", active_id=self.opportunity_1.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "crm.lead")
            self.assertEqual(form.lead_id, self.opportunity_1)
            self.assertEqual(form.res_ids, f"[{self.opportunity_1.id}]")
            self.assertEqual(form.call_id, call)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "crm.lead")

    def test_log_call_domain_covers_commercial_entity_crm(self):
        """The lead domain of the log activity wizard must cover opportunities
        related to every partner of the call contact's commercial entity."""
        company_partner = self.env["res.partner"].create({"name": "Wizard Company"})
        (
            self.partner_no_opportunities | self.partner_one_opportunity
        ).parent_id = company_partner.id
        sibling_opportunity = self.env["crm.lead"].create({
            "name": "Sibling Opportunity",
            "type": "opportunity",
            "partner_id": self.partner_no_opportunities.id,
            "user_id": self.user_sales_manager.id,
            "probability": 40,
        })
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=self.partner_one_opportunity.id,
        ).new()
        leads = self.env["crm.lead"].search(literal_eval(wizard.lead_id_domain))
        self.assertIn(self.opportunity_1, leads, "own opportunities stay selectable")
        self.assertIn(
            sibling_opportunity, leads,
            "opportunities of sibling contacts of the same company become selectable",
        )
        self.assertNotIn(
            self.opportunity_2, leads,
            "opportunities of partners outside the commercial entity stay hidden",
        )
