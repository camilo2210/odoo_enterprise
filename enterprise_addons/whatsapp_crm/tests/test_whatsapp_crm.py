# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.tests import users


class TestWhatsappCrm(WhatsAppCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_wa_admin.write({"group_ids": [(4, cls.env.ref("sales_team.group_sale_salesman").id)]})
        cls.partner = cls.env["res.partner"].create({"name": "Test Operator"})

    @users("user_wa_admin")
    def test_prepare_lead_create_values(self):
        channel = self.env["discuss.channel"].create({
            "name": "Test WA Channel",
            "channel_type": "whatsapp",
            "wa_account_id": self.whatsapp_account.id,
            "whatsapp_number": "+1234567890",
        })
        lead = self.env["crm.lead"].create(channel._prepare_lead_create_values(self.partner, "/lead Test Lead"))
        self.assertRecordValues(
            lead,
            [{
                'name': "Test Lead",
                'referred': self.partner.name,
                'source_id': self.env.ref("whatsapp.utm_source_whatsapp").id,
                'medium_id': self.env.ref("utm.utm_medium_messaging").id,
                'utm_reference': self.whatsapp_account,
            }]
        )
