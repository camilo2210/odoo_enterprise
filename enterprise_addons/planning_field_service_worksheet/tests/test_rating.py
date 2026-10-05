import json

from odoo import Command
from odoo.addons.mail.tests.common import MailCase
from odoo.addons.planning_field_service.tests.common import TestPlanningFieldServiceCommon
from odoo.tests.common import HttpCase


class TestPlanningFieldServiceWorksheetRating(TestPlanningFieldServiceCommon, HttpCase, MailCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Enable rating feature
        cls.env['res.config.settings'].create({'group_field_service_allow_customer_ratings': True}).execute()

        cls.partner_user = cls.env['res.users'].create({
            'partner_id': cls.partner.id,
            'login': 'partner',
            'group_ids': [Command.set(cls.env.ref('base.group_portal').ids)],
        })

    def test_rating_email_sent_after_signing_customer_report(self):
        worksheet_template = self.env['worksheet.template'].create({
            'name': 'New worksheet',
            'res_model': 'planning.slot',
            'worksheet_properties_definition': [{
                'name': 'a', 'type': 'char', 'string': 'Serial Number', 'default': False,
            }],
        })
        self.intervention.worksheet_template_id = worksheet_template.id
        self.intervention.worksheet_properties = {'a': 'b'}

        with self.mock_mail_gateway():
            self.intervention.with_user(self.george_user).action_complete()

        mail = self.env['mail.mail'].search([('recipient_ids', 'in', self.partner.id)])
        self.assertFalse(mail, 'No rating request email should have been sent to the partner')

        # Sign the report
        self.authenticate("partner", "partner")
        self.url_open(
            url=f'/my/field-service/{self.intervention.id}/sign',
            data=json.dumps({
                "params": {
                    'name': "Customer Name",
                    'access_token': self.intervention.access_token,
                    'signature': "R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs=",
                },
            }),
            headers={"Content-Type": "application/json"},
        )

        mails = self.env['mail.mail'].search([('recipient_ids', 'in', self.partner.id)])
        self.assertEqual(len(mails), 2, 'The customer request and intervention report emails should have been sent to the partner')
        self.assertEqual(len(mails.filtered(lambda m: "Service Rating Request" in m.subject)), 1)
        self.assertEqual(len(mails.filtered(lambda m: "Field Service Report" in m.subject)), 1)
