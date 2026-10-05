from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("voip", "at_install", "-post_install")
class TestVoipCallActivityAccess(TransactionCase):
    """A call may only be attached to an activity its owner is entitled to.

    ``create_and_format`` creates through ``sudo()`` and serialises the linked
    activity back to the caller, and ``update_activity_message`` rewrites that
    activity's chatter through ``sudo()``. Both take the activity from the
    client, so both have to establish the caller's claim on it themselves.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env["res.company"].create({"name": "Company A"})
        cls.company_b = cls.env["res.company"].create({"name": "Company B"})
        cls.attacker = new_test_user(
            cls.env, login="voip_outsider", groups="base.group_user",
            company_id=cls.company_a.id, name="Outsider",
        )
        cls.attacker.company_ids = [Command.set([cls.company_a.id])]
        cls.officer = new_test_user(
            cls.env, login="voip_officer_b", groups="voip.group_voip_officer",
            company_id=cls.company_a.id, name="Officer",
        )
        cls.officer.company_ids = [Command.set([cls.company_a.id])]
        cls.foreign_partner = cls.env["res.partner"].create({
            "name": "Confidential Prospect",
            "company_id": cls.company_b.id,
            "phone": "+32499000000",
        })
        cls.foreign_activity = cls.env["mail.activity"].create({
            "activity_type_id": cls.env.ref("mail.mail_activity_data_call").id,
            "res_model_id": cls.env["ir.model"]._get("res.partner").id,
            "res_id": cls.foreign_partner.id,
            "user_id": cls.officer.id,
            "summary": "Confidential call summary",
        })

    def test_foreign_activity_is_unreadable(self):
        with self.assertRaises(AccessError):
            self.foreign_activity.with_user(self.attacker).read(["summary"])

    def test_create_and_format_refuses_unreadable_activity(self):
        """Without this the activity, its record and its assignee are serialised
        back to a caller who cannot read any of them."""
        with self.assertRaises(AccessError):
            self.env["voip.call"].with_user(self.attacker).create_and_format(
                phone_number="+32400000000",
                activity_id=self.foreign_activity.id,
            )
        self.assertFalse(
            self.env["voip.call"].search([("activity_id", "=", self.foreign_activity.id)]),
            "no call may be attached to an activity the caller cannot read",
        )

    def test_create_and_format_accepts_own_activity(self):
        own_partner = self.env["res.partner"].create({
            "name": "Own Contact", "company_id": self.company_a.id, "phone": "+32499111111",
        })
        activity = self.env["mail.activity"].create({
            "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
            "res_model_id": self.env["ir.model"]._get("res.partner").id,
            "res_id": own_partner.id,
            "user_id": self.attacker.id,
            "summary": "My own call",
        })
        result = self.env["voip.call"].with_user(self.attacker).create_and_format(
            phone_number="+32400000000", activity_id=activity.id,
        )
        call = self.env["voip.call"].browse(result["ids"][0])
        self.assertEqual(call.activity_id, activity)
        self.assertIn("mail.activity", result["store_data"].as_dict())

    def test_update_activity_message_leaves_foreign_chatter_alone(self):
        """The call owner and the activity assignee must be the same person
        before the activity's chatter is rewritten under sudo."""
        call = self.env["voip.call"].create({
            "phone_number": "+32400000000",
            "user_id": self.attacker.id,
            "activity_id": self.foreign_activity.id,
        })
        messages = self.foreign_activity.with_user(self.officer)._action_done(feedback="done")
        call.invalidate_recordset()
        message = call.activity_mail_message_id
        self.assertEqual(message, messages, "the assignee's completion links its message")

        body_before = message.body
        call.with_user(self.attacker).update_activity_message()
        message.invalidate_recordset()
        self.assertEqual(
            message.body, body_before,
            "an outsider must not rewrite the chatter of another user's activity",
        )
