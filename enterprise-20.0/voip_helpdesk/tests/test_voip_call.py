from ast import literal_eval

from odoo.tests import Form, users

from .common import VoipHelpdeskCommon


class TestVoipCall(VoipHelpdeskCommon):
    def test_action_log_call_with_mismatched_record_helpdesk(self):
        """When the ticket's partner differs from the call's partner, the
        domain check fails and the wizard falls back to the call's contact."""
        other_partner = self.env["res.partner"].create({"name": "Other Partner"})
        ticket_other = self.env["helpdesk.ticket"].create({
            "name": "Ticket Other",
            "partner_id": other_partner.id,
        })
        with Form.from_action(
            self.env, self.call_1.action_log_call(active_model="helpdesk.ticket", active_id=ticket_other.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "res.partner")
            self.assertEqual(form.contact_id, self.partner)
            self.assertEqual(form.res_ids, f"[{self.partner.id}]")
            self.assertEqual(form.call_id, self.call_1)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "res.partner")

    def test_log_call_domain_covers_commercial_entity_helpdesk(self):
        """The ticket domain of the log activity wizard must cover tickets of
        the whole commercial entity: the contact's own tickets, the company's
        own tickets and sibling contacts' tickets."""
        company_ticket = self.env["helpdesk.ticket"].create({
            "name": "Company Ticket",
            "partner_id": self.company_partner.id,
            "user_id": self.helpdesk_user.id,
            "stage_id": self.stage_new.id,
        })
        sibling_partner = self.env["res.partner"].create({
            "name": "Sibling Partner",
            "parent_id": self.company_partner.id,
        })
        sibling_ticket = self.env["helpdesk.ticket"].create({
            "name": "Sibling Ticket",
            "partner_id": sibling_partner.id,
            "user_id": self.helpdesk_user.id,
            "stage_id": self.stage_new.id,
        })
        unrelated_partner = self.env["res.partner"].create({"name": "Unrelated Partner"})
        unrelated_ticket = self.env["helpdesk.ticket"].create({
            "name": "Unrelated Ticket",
            "partner_id": unrelated_partner.id,
            "user_id": self.helpdesk_user.id,
            "stage_id": self.stage_new.id,
        })
        wizard = self.env["mail.activity.schedule"].with_context(
            voip_log_contact_id=self.partner.id,
        ).new()
        tickets = self.env["helpdesk.ticket"].search(literal_eval(wizard.ticket_id_domain))
        self.assertIn(self.ticket_open_1, tickets, "own tickets stay selectable")
        self.assertIn(company_ticket, tickets, "tickets of the commercial partner become selectable")
        self.assertIn(
            sibling_ticket, tickets,
            "tickets of sibling contacts of the same company become selectable",
        )
        self.assertNotIn(
            unrelated_ticket, tickets,
            "tickets of partners outside the commercial entity stay hidden",
        )

    @users("user_helpdesk_user")
    def test_action_log_call_with_matching_model_helpdesk(self):
        """When active_model=helpdesk.ticket matches a registered option,
        the wizard should pre-select that record type and record."""
        call = self.call_1.with_env(self.env)
        ticket = self.env["helpdesk.ticket"].create({
            "name": "Test Ticket",
            "partner_id": self.partner.id,
            "user_id": self.env.user.id,
        })
        with Form.from_action(
            self.env, call.action_log_call(active_model="helpdesk.ticket", active_id=ticket.id),
        ) as form:
            self.assertEqual(form.res_model_selection, "helpdesk.ticket")
            self.assertEqual(form.ticket_id, ticket)
            self.assertEqual(form.res_ids, f"[{ticket.id}]")
            self.assertEqual(form.call_id, self.call_1)
            # NB: defaults do not trigger the inverse; res_model is only
            # synced on create/write, i.e. when the user marks the activity done.
            form.save()
            self.assertEqual(form.res_model, "helpdesk.ticket")

    @users("user_helpdesk_user")
    def test_voip_call_commercial_partner_ticket_count_user(self):
        partner = self.partner.with_env(self.env)
        call = self.call_1.with_env(self.env)
        self.assertEqual([partner.commercial_partner_ticket_count, partner.commercial_partner_open_ticket_count], [call.commercial_partner_ticket_count, call.commercial_partner_open_ticket_count],
                         "The commercial partner ticket counts on the call should match those on the partner.")

    @users("user_helpdesk_manager")
    def test_voip_call_commercial_partner_ticket_count_manager(self):
        partner = self.partner.with_env(self.env)
        call = self.call_2.with_env(self.env)
        self.assertEqual([partner.commercial_partner_ticket_count, partner.commercial_partner_open_ticket_count], [call.commercial_partner_ticket_count, call.commercial_partner_open_ticket_count],
                         "The commercial partner ticket counts on the call should match those on the partner.")

    def test_voip_action_open_helpdesk_ticket_uses_commercial_partner(self):
        """Smart button should open tickets from the whole partner family (commercial partner)."""
        self.assertEqual(self.call_1.commercial_partner_ticket_count, self.company_partner.ticket_count)
        action = self.call_1.voip_action_open_helpdesk_ticket()
        tickets = self.env["helpdesk.ticket"].search(action["domain"])
        self.assertEqual(len(tickets), self.call_1.commercial_partner_ticket_count)
