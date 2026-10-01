from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.tests import users, tagged


@tagged("marketing_automation", "ma_enroll", "ma_enroll_action")
class TestMAMailingList(MarketingAutomationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_mailing_list()
        cls.campaign_ml1, cls.campaign_ml2 = cls.env["marketing.campaign"].create([
            {
                "name": "Campaign Mailing List 1",
                "enroll_type": "action",
                "enroll_action_type": "subscribe",
                "mailing_list_ids": [(6, 0, [cls.mailing_list_1.id])],
                "model_id": cls.env["ir.model"]._get_id("res.partner"),
            }, {
                "name": "Campaign Mailing List 2",
                "enroll_type": "action",
                "enroll_action_type": "subscribe",
                "mailing_list_ids": [(6, 0, [cls.mailing_list_2.id])],
                "model_id": cls.env["ir.model"]._get_id("res.partner"),
            }
        ])
        cls._create_activity_mail(cls.campaign_ml1)
        cls._create_activity_mail(cls.campaign_ml2)

    @users("user_marketing_automation")
    def test_mailing_update_optout(self):
        self._launch_campaign(self.campaign_ml1)
        email_formatted = '"Mireille Labeille" <mireille@test.example.com>'
        ml_1, ml_2 = self.mailing_list_1.with_env(self.env), self.mailing_list_2.with_env(self.env)

        mailing_contact = self.env['mailing.contact'].browse(self.env['mailing.contact'].name_create(email_formatted)[0])
        mailing_contact.partner_id = self.env['res.partner'].find_or_create(email_formatted).id

        (ml_1 + ml_2)._update_subscription_from_email(email_formatted, opt_out=False)

        participants = self.env["marketing.participant"].search([("campaign_id", "in", (self.campaign_ml1 + self.campaign_ml2).ids)])

        self.assertEqual(set(participants.mapped("res_id")), set(mailing_contact.partner_id.ids))
