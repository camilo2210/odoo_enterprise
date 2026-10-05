from odoo import fields
from odoo.tests.common import HttpCase
from odoo.addons.mail.tests.common import MailCase

from .common import TestPlanningFieldServiceCommon


class TestPlanningFieldServiceRating(TestPlanningFieldServiceCommon, HttpCase, MailCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Enable rating feature
        cls.env['res.config.settings'].create({'group_field_service_allow_customer_ratings': True}).execute()

        cls.test_slot = cls.env['planning.slot'].with_context({'mail_create_nolog': True}).create({
            'name': 'Field Service Slot',
            'partner_id': cls.partner.id,
            'resource_ids': cls.george_employee.resource_id.ids,
            'start_datetime': fields.Datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': fields.Datetime.now().replace(hour=12, minute=0, second=0),
            'state': '2_published',
        })

        cls.default_rating_vals = {
            'res_model_id': cls.env['ir.model']._get('planning.slot').id,
            'partner_id': cls.partner.id,
            'consumed': True,
        }

    def test_rating_notification(self):
        self.assertFalse(self.test_slot.rating_ids, 'No rating should have ben applied to the slot')

        self.env['rating.rating'].create({
            **self.default_rating_vals,
            'rated_partner_id': self.george_user.partner_id.id,
            'res_id': self.test_slot.id,
            'consumed': False,
            'access_token': 'RATING_TEST',
        })

        rating = 5
        feedback = 'Great!'

        self.test_slot.rating_apply(rating, token='RATING_TEST', feedback=feedback)
        message = self.test_slot.message_ids

        self.assertEqual(len(message), 1, 'A message should have been posted in the chatter.')
        self.assertEqual(message.author_id, self.partner, 'The message should be posted by the rating partner.')
        self.assertIn(f"{rating}/5", message.body, f"The posted rating should be {rating}/5.")
        self.assertIn(feedback, message.body, 'The posted rating should contain the customer feedback.')
        self.assertTrue(self.test_slot.rating_ids, 'A rating should have ben applied to the slot')

    def test_rating_email_is_not_sent_if_setting_is_not_enabled(self):
        self.env['res.config.settings'].create({'group_field_service_allow_customer_ratings': False}).execute()

        with self.mock_mail_gateway():
            self.test_slot.with_user(self.george_user).action_complete()

        message = self.test_slot.message_ids
        self.assertFalse(message, 'No message should have been posted in the chatter.')

        mail = self.env['mail.mail'].search([('recipient_ids', 'in', self.partner.id)])
        self.assertFalse(mail, 'No rating request email should have been sent to the partner')

    def test_rating_email_sent_on_action_complete(self):
        with self.mock_mail_gateway():
            self.test_slot.with_user(self.george_user).action_complete()

        message = self.test_slot.message_ids
        self.assertEqual(len(message), 1, 'A message should have been posted in the chatter.')
        self.assertIn("Service Rating Request", message.subject)

        mail = self.env['mail.mail'].search([('recipient_ids', 'in', self.partner.id)])
        self.assertEqual(len(mail), 1, 'The customer request email should have been sent to the partner')
        self.assertIn("Service Rating Request", mail.subject)
