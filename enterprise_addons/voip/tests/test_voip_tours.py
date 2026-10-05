import unittest

from datetime import date

from odoo.tests import HttpCase


class TestVoipTours(HttpCase):
    def setUp(self):
        super().setUp()
        self.env.ref("base.user_admin").res_users_settings_id.with_context(
            voip_skip_pbx_sync=True,
        ).voip_provider_id = self.env.ref("voip.default_voip_provider")

    def test_voip_call_duration_views_tour(self):
        partners = self.env["res.partner"].create([
            {"name": "VOIP Duration Tour Contact"},
            {"name": "Some other contact"},
        ])
        calls = self.env["voip.call"].create([
            {
                "phone_number": "01123581321345589144",
                "partner_id": partners[0].id,
                "state": "terminated",
                "user_id": self.env.ref("base.user_admin").id,
                "duration": 123,
            },
            {
                "phone_number": "01123581321345589144",
                "partner_id": partners[1].id,
                "state": "terminated",
                "user_id": self.env.ref("base.user_admin").id,
                "duration": 10,
            },
        ])
        action = self.env.ref("voip.voip_call_view").copy({
            "domain": [("id", "in", calls.ids)],
        })
        self.start_tour(
            f"/odoo/action-{action.id}",
            "voip_call_duration_views_tour",
            login="admin",
        )

    def test_no_content_softphone_tour(self):
        """The empty Calls list offers a link opening the softphone."""
        admin = self.env.ref("base.user_admin")
        # Remove the existing calls (demo data) to get an empty list.
        self.env["voip.call"].search([("user_id", "=", admin.id)]).unlink()
        action = self.env.ref("voip.voip_call_view")
        self.start_tour(
            f"/odoo/action-{action.id}",
            "voip_no_content_softphone_tour",
            login="admin",
        )

    def test_country_selector_tour(self):
        self.start_tour("/odoo", "country_selector_tour", login="admin")

    # FIXME this test works 100% of the time in local, and does fail 100% of the
    # time if the related feature is broken... but for some reason it does not
    # work on runbot.
    @unittest.skip
    def test_keypad_tour(self):
        self.start_tour("/odoo", "keypad_tour", login="admin")

    def test_call_activity_chatter(self):
        """Check when a call activity is marked as done by placing a phone call,
        the link to the call is posted in the chatter of the related record.
        """
        test_partner = self.env["res.partner"].create({
            "name": "Police",
            "phone": "110",
        })
        self.env["mail.activity"].create({
            "res_model_id": self.env['ir.model']._get_id('res.partner'),
            "res_id": test_partner.id,
            "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
            "user_id": self.env.ref("base.user_admin").id,
            "date_deadline": date.today(),
        })
        self.start_tour("/odoo", "call_activity_chatter_link", login="admin")

    def test_voip_log_after_call_tour(self):
        self.env["res.partner"].create({
            "name": "Police",
            "phone": "110",
        })
        self.start_tour("/odoo", "voip_log_after_call_tour", login="admin")

    def test_voip_log_during_call_tour(self):
        self.env["res.partner"].create({
            "name": "Ambulance",
            "phone": "120",
        })
        self.start_tour("/odoo", "voip_log_during_call_tour", login="admin")
