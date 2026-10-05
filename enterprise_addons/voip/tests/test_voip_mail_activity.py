from ast import literal_eval

from odoo.tests import Form, common, tagged


@tagged("voip", "post_install", "-at_install")
class TestVoipMailActivity(common.TransactionCase):
    def test_voip_mail_activity_phone_country_mixin(self):
        """Tests that "phone_country_id" is properly computed based on a phone field"""
        some_partner = self.env["res.partner"].create({"name": "Some partner", "phone": "+493023125513"})
        activity = some_partner.activity_schedule("mail.mail_activity_data_call")
        self.assertEqual(activity.phone_country_id.code, "DE")

    def test_voip_activity_schedule_contact_id_editable_with_partner(self):
        """When opening the activity schedule from a call that HAS a partner,
        the contact_id field defaults to the call's partner but stays editable,
        e.g. to log on another contact of the same company."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        call = self.env["voip.call"].create({
            "phone_number": "123456789",
            "direction": "incoming",
            "state": "ongoing",
            "partner_id": partner.id,
        })
        action = call.action_log_call()
        form = Form.from_action(self.env, action)
        self.assertEqual(form.contact_id, partner)
        self.assertFalse(
            form._get_modifier('contact_id', 'readonly'),
            "contact_id should be editable even when call has a partner",
        )

    def test_voip_activity_schedule_contact_id_editable_without_partner(self):
        """When opening the activity schedule from a call WITHOUT a partner,
        the contact_id field should be editable because voip_log_contact_id
        is falsy in the context."""
        call = self.env["voip.call"].create({
            "phone_number": "987654321",
            "direction": "incoming",
            "state": "ongoing",
        })
        action = call.action_log_call()
        form = Form.from_action(self.env, action)
        self.assertFalse(
            form._get_modifier('contact_id', 'readonly'),
            "contact_id should be editable when call has no partner",
        )

    def test_voip_activity_schedule_sets_call_partner_from_partner(self):
        """When logging a call without partner on a res.partner, the call's
        partner_id should be set to that partner."""
        call = self.env["voip.call"].create({
            "phone_number": "111222333",
            "direction": "incoming",
            "state": "ongoing",
        })
        target_partner = self.env["res.partner"].create({"name": "Target Partner"})

        action = call.action_log_call()
        form = Form.from_action(self.env, action)
        form.contact_id = target_partner
        wizard = form.save()
        wizard._action_schedule_activities()
        self.assertEqual(
            call.partner_id,
            target_partner,
            "call.partner_id should be set to the contact selected in the wizard",
        )

    def test_update_activity_message_renders_feedback(self):
        partner = self.env["res.partner"].create({"name": "Feedback Partner"})
        activity = self.env["mail.activity"].create({
            "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
            "res_model_id": self.env["ir.model"]._get("res.partner").id,
            "res_id": partner.id,
            "user_id": self.env.user.id,
        })
        call = self.env["voip.call"].create({
            "phone_number": "+32400000000",
            "user_id": self.env.user.id,
            "activity_id": activity.id,
        })
        messages = activity._action_done(feedback="My feedback text")
        call.invalidate_recordset()
        message = call.activity_mail_message_id
        self.assertEqual(message, messages)
        call.update_activity_message()
        message.invalidate_recordset()
        self.assertIn("My feedback text", message.body)

    def test_voip_activity_schedule_contact_id_domain_covers_commercial_entity(self):
        """The contact domain must cover the whole commercial entity but
        exclude archived partners, as activities are not logged on them."""
        company = self.env["res.partner"].create({"name": "Wizard Company"})
        main = self.env["res.partner"].create({"name": "Main Contact", "parent_id": company.id})
        sibling = self.env["res.partner"].create({"name": "Sibling Contact", "parent_id": company.id})
        archived = self.env["res.partner"].create({"name": "Archived Contact", "parent_id": company.id})
        archived.active = False
        unrelated = self.env["res.partner"].create({"name": "Unrelated Contact"})
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=main.id,
        ).new()
        contacts = self.env["res.partner"].search(literal_eval(wizard.contact_id_domain))
        self.assertIn(main, contacts)
        self.assertIn(sibling, contacts, "sibling contacts of the same company become selectable")
        self.assertIn(company, contacts)
        self.assertNotIn(archived, contacts, "archived partners stay hidden")
        self.assertNotIn(unrelated, contacts)
