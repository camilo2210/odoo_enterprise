# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
import io

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged, Form, users
from odoo.tests.common import new_test_user
from odoo.tools import formataddr
from odoo.tools.pdf import PdfFileReader, PdfFileWriter

from odoo.addons.base.tests.common import HttpCaseWithUserDemo
from odoo.addons.mail.tests.common import MockEmail
from odoo.addons.mail.tools.discuss import Store
from reportlab.pdfgen import canvas
from .sign_request_common import SignRequestCommon
from unittest.mock import patch


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestSignRequest(SignRequestCommon, MockEmail):
    def test_sign_request_create(self):
        sign_request_no_item = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)

        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)

        for sign_request in [sign_request_no_item, sign_request_3_roles]:
            self.assertTrue(sign_request.exists(), 'A sign request with no sign item should be created')
            self.assertEqual(sign_request.state, 'sent', 'The default state for a new created sign request should be "sent"')
            self.assertTrue(all(sign_request.request_item_ids.mapped('is_mail_sent')), 'The mail should be sent for the new created sign request by default')
            self.assertEqual(sign_request.with_context(active_test=False).cc_partner_ids, self.partner_4, 'The cc_partners should be the specified one and the creator unless the creator is inactive')
            self.assertEqual(len(sign_request.sign_log_ids.filtered(lambda log: log.action == 'create')), 1, 'A log with action="create" should be created')
            for sign_request_item in sign_request:
                self.assertEqual(sign_request_item.state, 'sent', 'The default state for a new created sign request item should be "sent"')
        self.assertEqual(len(sign_request_no_item.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity should be scheduled for signers with Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity should be scheduled for signers with Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 1, 'An activity should be scheduled for signers with Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_5.id)), 0, 'An activity should not be scheduled for signers without Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_4.id)), 0, 'An activity should not be scheduled for CC partners')

        SignRequest = self.env['sign.request']
        with self.assertRaises(ValidationError, msg='A sign request with no sign item needs a signer'):
            SignRequest.create({
                'template_id': self.template_no_item.id,
                'reference': self.template_no_item.display_name,
            })

        with self.assertRaises(ValidationError, msg='A sign request with no sign item can only have the default role'):
            SignRequest.create({
                'template_id': self.template_no_item.id,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_3.id,
                })],
                'reference': self.template_no_item.display_name,
            })

        with self.assertRaises(ValidationError, msg='Three roles need three singers'):
            SignRequest.create({
                'template_id': self.template_3_roles.id,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_1.id,
                }), Command.create({
                    'partner_id': self.partner_2.id,
                    'role_id': self.role_signer_2.id,
                })],
                'reference': self.template_3_roles.display_name,
            })

        with self.assertRaises(ValidationError, msg='A role cannot be shared with two signers'):
            SignRequest.create({
                'template_id': self.template_3_roles.id,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_1.id,
                }), Command.create({
                    'partner_id': self.partner_2.id,
                    'role_id': self.role_signer_2.id,
                }), Command.create({
                    'partner_id': self.partner_3.id,
                    'role_id': self.role_signer_3.id,
                }), Command.create({
                    'partner_id': self.partner_4.id,
                    'role_id': self.role_signer_3.id,
                })],
                'reference': self.template_3_roles.display_name,
            })

    def test_sign_request_no_item_create_sign_cancel_copy(self):
        # create
        sign_request_no_item = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        sign_request_item = sign_request_no_item.request_item_ids[0]

        # sign
        with self.assertRaises(UserError, msg='A sign.request.item can only sign its sign.items'):
            sign_request_item.sign(self.signer_1_sign_values)
        sign_request_item.sign(self.signature_fake)
        self.assertEqual(sign_request_item.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_no_item.state, 'signed', 'The sign request should be signed')
        self.assertEqual(len(sign_request_no_item.completed_document_attachment_ids), 2, 'The completed document and the certificate should be created')
        self.assertEqual(len(sign_request_no_item.sign_log_ids.filtered(
            lambda log: log.action == 'sign' and log.sign_request_item_id == sign_request_item)),
            1, 'A log with action="sign" should be created')
        self.assertEqual(len(sign_request_no_item.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 0, 'The activity should be removed after signing')
        with self.assertRaises(UserError, msg='A document cannot be signed twice'):
            sign_request_item.sign(self.signature_fake)

        # unlink
        with self.assertRaises(UserError, msg='A signed sign request cannot be unlinked'):
            sign_request_no_item.unlink()

        # cancel
        sign_request_no_item.cancel()
        self.assertEqual(sign_request_item.state, 'completed', 'The sign.request.item should be completed')

        # copy
        new_sign_request_no_item = sign_request_no_item.copy()
        self.assertTrue(new_sign_request_no_item.exists(), 'A sign request with no sign item should be created')
        self.assertEqual(new_sign_request_no_item.state, 'sent', 'The default state for a new created sign request should be "sent"')
        self.assertTrue(all(new_sign_request_no_item.request_item_ids.mapped('is_mail_sent')), 'The mail should be sent for the new created sign request by default')
        self.assertEqual(new_sign_request_no_item.with_context(active_test=False).cc_partner_ids, self.partner_4, 'The cc_partners should be the specified one and the creator unless he is inactive')
        self.assertEqual(len(new_sign_request_no_item.sign_log_ids.filtered(lambda log: log.action == 'create')), 1, 'A log with action="create" should be created')
        for sign_request_item in new_sign_request_no_item:
            self.assertEqual(sign_request_item.state, 'sent', 'The default state for a new created sign request item should be "sent"')
        self.assertNotEqual(new_sign_request_no_item.access_token, sign_request_no_item.access_token, 'The access_token should be changed')
        self.assertNotEqual(new_sign_request_no_item.request_item_ids[0].access_token, sign_request_no_item.request_item_ids[0].access_token, 'The access_token should be changed')

    def test_sign_request_3_roles_create_sign_cancel(self):
        # create
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]

        # sign
        with self.assertRaises(UserError, msg='A sign.request.item can only sign its sign.items'):
            sign_request_item_signer_2.sign(self.signer_1_sign_values)
        sign_request_item_signer_1.sign(self.signer_1_sign_values)
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'sent', 'The sign.request.item should be sent')
        self.assertEqual(sign_request_item_signer_3.state, 'sent', 'The sign.request.item should be sent')
        self.assertEqual(sign_request_3_roles.state, 'sent', 'The sign request should be signed')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(
            lambda log: log.action == 'sign' and log.sign_request_item_id == sign_request_item_signer_1)),
            1, 'A log with action="sign" should be created')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 0, 'The activity should be removed after signing')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 1, 'The activity should not be removed for unsigned signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 1, 'The activity should not be removed for unsigned signer')
        with self.assertRaises(UserError, msg='A document cannot be signed twice'):
            sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # cancel
        sign_request_item_signer_1_token = sign_request_item_signer_1.access_token
        sign_request_item_signer_2_token = sign_request_item_signer_2.access_token
        sign_request_item_signer_3_token = sign_request_item_signer_3.access_token
        sign_request_3_roles_token = sign_request_3_roles.access_token
        sign_request_3_roles.cancel()
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_item_signer_3.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_3_roles.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item_signer_1.access_token, sign_request_item_signer_1_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_2.access_token, sign_request_item_signer_2_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_3.access_token, sign_request_item_signer_3_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_3_roles.access_token, sign_request_3_roles_token, 'The access token should be changed')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(lambda log: log.action == 'cancel')), 1, 'A log with action="cancel" should be created')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'The activity should be removed after cancellation')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 0, 'The activity should be removed after cancellation')

    def test_sign_request_3_roles_create_sign_refuse_cancel(self):
        # create
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]

        # sign (test has been done in test_sign_request_3_roles_create_sign_cancel)
        sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # refuse
        with self.assertRaises(UserError, msg='A signed sign.request.item cannot be refused'):
            sign_request_item_signer_1._refuse(request_state='sent', refusal_reason="bad document")
        sign_request_item_signer_1_token = sign_request_item_signer_1.access_token
        sign_request_item_signer_2_token = sign_request_item_signer_2.access_token
        sign_request_item_signer_3_token = sign_request_item_signer_3.access_token
        sign_request_3_roles_token = sign_request_3_roles.access_token
        sign_request_item_signer_2._refuse(request_state='sent', refusal_reason='bad document')
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'canceled', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_3.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_3_roles.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item_signer_1.access_token, sign_request_item_signer_1_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_2.access_token, sign_request_item_signer_2_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_3.access_token, sign_request_item_signer_3_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_3_roles.access_token, sign_request_3_roles_token, 'The access token should be changed')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(
            lambda log: log.action == 'refuse' and log.sign_request_item_id == sign_request_item_signer_2)),
            1, 'A log with action="refuse" should be created')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'The activity should be removed for refused signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 0, 'The activity should be removed for remaining signers')

        with self.assertRaises(UserError, msg='A canceled sign.request.item cannot be signed'):
            sign_request_item_signer_3.sign(self.signer_3_sign_values)

        # cancel
        sign_request_3_roles.cancel()
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'canceled', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_3.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_3_roles.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item_signer_1.access_token, sign_request_item_signer_1_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_2.access_token, sign_request_item_signer_2_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_3.access_token, sign_request_item_signer_3_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_3_roles.access_token, sign_request_3_roles_token, 'The access token should be changed')
        # now the cancel method is also called from refuse method so the log count is become 2
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(lambda log: log.action == 'cancel')), 2, 'A log with action="cancel" should be created')

    def test_sign_request_refuse_shared(self):
        """ Ensure that shared sign requests can be refused by public users. """
        # Get the shared request from a template with one role.
        wizard_id = self.template_1_role.open_shared_sign_request()['res_id']
        wizard = self.env['sign.request.share'].browse(wizard_id)
        shared_request = wizard.sign_request_id
        sign_request_item = shared_request.request_item_ids[0]

        with self.assertRaises(UserError):
            # Ensure an user error is raised by not specifying the refusal email.
            sign_request_item.with_user(self.public_user).sudo()._refuse(
                request_state="shared",
                refusal_reason="Reason",
                refusal_name="Marc"
            )

        sign_request_item.with_user(self.public_user).sudo()._refuse(
            request_state="shared",
            refusal_reason="Reason",
            refusal_name="Marc",
            refusal_email="demo@odoo.com"
        )
        self.assertEqual(shared_request.state, "shared", "Previous request must remain shared.")

        refused_public_user = self.env['res.partner'].search([('email', '=', 'demo@odoo.com')])
        self.assertTrue(refused_public_user, "Ensure that the partner from the public user was created.")

        refused_request_item = self.env['sign.request.item'].search([('partner_id', '=', refused_public_user.id)])
        self.assertEqual(len(refused_request_item), 1, "Ensure that the refused request item was created.")

        refused_request = self.env['sign.request'].search([
            ('state', '=', 'canceled'),
            ('id', '>', shared_request.id)
        ])
        self.assertEqual(len(refused_request), 1, "Ensure that the refused request was created.")

    def test_sign_request_item_auto_resend(self):
        # create
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        request_item_ids = sign_request.request_item_ids
        request_item = request_item_ids[0]
        token_a = request_item.access_token
        self.assertEqual(request_item.signer_email, "laurie.poiret.a@example.com", 'email address should be laurie.poiret.a@example.com')
        self.assertEqual(request_item.is_mail_sent, True, 'email should be sent')

        # resend the document
        request_item.send_signature_accesses()
        self.assertEqual(request_item.access_token, token_a, "sign request item's access token should not be changed")

        # change the email address of the signer (laurie.poiret.b)
        with self.assertRaises(ValidationError, msg='All signers must have valid email addresses'):
            self.partner_1.write({'email': 'laurie.poiret.b'})

        # change the email address to upper case (LAURIE.POIRET.A@example.com)
        self.partner_1.write({'email': 'LAURIE.POIRET.A@example.com'})
        self.assertEqual(request_item.signer_email, "laurie.poiret.a@example.com", 'email address should not be changed as is the same email')
        self.assertFalse(
            sign_request.sign_log_ids.filtered(lambda log: log.action == 'update_mail' and log.sign_request_item_id == request_item),
            'No log with action="update_mail" should be created after changing the email to upper case'
        )

        # change the email address of the signer (laurie.poiret.b@example.com)
        self.partner_1.write({'email': 'laurie.poiret.b@example.com'})
        token_b = request_item.access_token
        self.assertEqual(request_item.signer_email, "laurie.poiret.b@example.com", 'email address should be laurie.poiret.b@example.com')
        self.assertNotEqual(token_b, token_a, "sign request item's access token should be changed")
        self.assertEqual(len(sign_request.sign_log_ids.filtered(
            lambda log: log.action == 'update_mail' and log.sign_request_item_id == request_item)),
            1, 'A log with action="update_mail" should be created')
        self.assertEqual(len(sign_request.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'The number of activities should still be 1')

        # sign the document
        request_item.sign(self.signature_fake)
        self.assertEqual(request_item.signer_email, "laurie.poiret.b@example.com", 'email address should be laurie.poiret.b@example.com')

        # change the email address of the signer (laurie.poiret.c@example.com)
        self.partner_1.write({'email': 'laurie.poiret.c@example.com'})
        token_c = request_item.access_token
        self.assertEqual(request_item.signer_email, "laurie.poiret.b@example.com", 'email address should be laurie.poiret.b@example.com')
        self.assertEqual(token_c, token_b, "sign request item's access token should be not changed after the document is signed by the signer")
        self.assertEqual(len(sign_request.sign_log_ids.filtered(
            lambda log: log.action == 'update_mail' and log.sign_request_item_id == request_item)),
            1, 'No new log with action="update_mail" should be created')

    def test_sign_request_item_reassign_sign_reassign_refuse_reassign(self):
        # create
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2,
                                                                signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]

        # reassign
        self.assertEqual(sign_request_item_signer_1.signer_email, "laurie.poiret.a@example.com", 'email address should be laurie.poiret.a@example.com')
        self.assertEqual(sign_request_item_signer_1.is_mail_sent, True, 'email should be sent')
        token_signer_1 = sign_request_item_signer_1.access_token
        with self.assertRaises(UserError, msg='Reassigning a role without change_authorized is not allowed'):
            sign_request_item_signer_1.write({'partner_id': self.partner_5.id})
        sign_request_item_signer_1.role_id.change_authorized = True
        with self.assertRaises(UserError, msg='Reassigning the partner_id to False is not allowed'):
            sign_request_item_signer_1.write({'partner_id': False})
        logs_num = len(sign_request_3_roles.sign_log_ids)
        sign_request_item_signer_1.write({'partner_id': self.partner_5.id})
        self.assertEqual(sign_request_item_signer_1.signer_email, "char.aznable.a@example.com", 'email address should be char.aznable.a@example.com')
        self.assertNotEqual(sign_request_item_signer_1.access_token, token_signer_1, "sign request item's access token should be changed")
        self.assertEqual(sign_request_item_signer_1.is_mail_sent, True, 'email should be sent')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids), logs_num, 'No new log should be created')
        self.assertEqual(sign_request_3_roles.with_context(active_test=False).cc_partner_ids, self.partner_4 + self.partner_1, 'If a signer is reassigned and no longer be a signer, he should be a contact in copy')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 0, 'The activity for the old signer should be removed')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_5.id)), 0, 'No activity should be created for user without permission to access Sign')

        # sign
        sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # reassign
        token_signer_2 = sign_request_item_signer_1.access_token
        with self.assertRaises(UserError, msg='A signed sign request item cannot be reassigned'):
            sign_request_item_signer_1.write({'partner_id': self.partner_1.id})
        sign_request_item_signer_2.role_id.change_authorized = True
        logs_num = len(sign_request_3_roles.sign_log_ids)
        sign_request_item_signer_2.write({'partner_id': self.partner_1.id})
        self.assertEqual(sign_request_item_signer_2.signer_email, "laurie.poiret.a@example.com", 'email address should be laurie.poiret.a@example.com')
        self.assertNotEqual(sign_request_item_signer_2.access_token, token_signer_2, "sign request item's access token should be changed")
        self.assertEqual(sign_request_item_signer_2.is_mail_sent, True, 'email should be sent')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids), logs_num, 'No new log should be created')
        self.assertEqual(sign_request_3_roles.with_context(active_test=False).cc_partner_ids, self.partner_4 + self.partner_2, 'If a signer is reassigned and no longer be a signer, he should be a contact in copy')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'The activity for the old signer should be removed')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity for the new signer should be created')

        # refuse
        sign_request_item_signer_2._refuse(request_state='sent', refusal_reason='bad request')

        # reassign
        with self.assertRaises(UserError, msg='A refused sign request item cannot be reassigned'):
            sign_request_item_signer_2.write({'partner_id': self.partner_2.id})
        with self.assertRaises(UserError, msg='A canceled sign request item cannot be reassigned'):
            sign_request_item_signer_3.write({'partner_id': self.partner_2.id})

    def test_sign_request_mail_sent_order(self):
        sign_request_3_roles = self.env['sign.request'].create({
            'template_id': self.template_3_roles.id,
            'reference': self.template_3_roles.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.role_signer_1.id,
                'mail_sent_order': 1,
            }), Command.create({
                'partner_id': self.partner_2.id,
                'role_id': self.role_signer_2.id,
                'mail_sent_order': 2,
            }), Command.create({
                'partner_id': self.partner_3.id,
                'role_id': self.role_signer_3.id,
                'mail_sent_order': 2,
            })],
        })
        self.partner_4.user_ids.notification_type = 'inbox'
        sign_request_3_roles.message_subscribe(partner_ids=[self.partner_4.id])
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity should be scheduled for the first signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'No activity should be scheduled for the second signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 0, 'No activity should be scheduled for the third signer')
        self.assertTrue(sign_request_item_signer_1.is_mail_sent, 'An email should be sent for the first signer')
        self.assertFalse(sign_request_item_signer_2.is_mail_sent, 'No email should be sent for the second signer')
        self.assertFalse(sign_request_item_signer_3.is_mail_sent, 'No email should be sent for the third signer')

        # sign
        sign_request_item_signer_1.sign(self.signer_1_sign_values)
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 1, 'An activity should be scheduled for the second signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 1, 'An activity should be scheduled for the third signer')
        self.assertTrue(sign_request_item_signer_2.is_mail_sent, 'An email should be sent for the second signer')
        self.assertTrue(sign_request_item_signer_3.is_mail_sent, 'An email should be sent for the third signer')

        # sign and sign
        sign_request_item_signer_2.sign(self.signer_2_sign_values)
        sign_request_item_signer_3.sign(self.signer_3_sign_values)
        self.assertEqual(sign_request_3_roles.state, 'signed', 'The sign request should be signed')
        notification = self.env['mail.message'].search([('partner_ids', '=', self.partner_4.id)])
        self.assertEqual(notification.subject, 'template_3_roles has been signed')

    def test_sign_request_mail_reply_to_exists(self):
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        responsible_email = sign_request.create_uid.email_formatted
        mail = sign_request._message_send_mail(
            "body",
            record_name=sign_request.reference,
            notif_values={
                'model_description': 'signature',
                'company': self.env.company,
                'partner': sign_request.request_item_ids[0].partner_id,
            },
            mail_values={
                'attachment_ids': [],
                'subject': sign_request.subject
            },
        )

        self.assertEqual(mail.reply_to, responsible_email, 'reply_to is not set as the responsible email')

    def test_sign_send_request_without_order(self):
        wizard = Form(self.env['sign.send.request'].with_context(default_template_id=self.template_3_roles.id, sign_directly_without_mail=False))
        self.assertEqual([record['mail_sent_order'] for record in wizard.signer_ids._records], [1, 1, 1])

    def test_sign_send_request_order_with_order(self):
        wizard = Form(self.env['sign.send.request'].with_context(default_template_id=self.template_3_roles.id, sign_directly_without_mail=False))
        wizard.set_sign_order = True
        self.assertEqual([record['mail_sent_order'] for record in wizard.signer_ids._records], [1, 2, 3])

    def test_archived_requests_dont_send_reminders(self):
        """ Create a request with a validity period and archive it, jump to the future
        where it's not valid anymore, trigger cron reminder and ensure no reminder was created. """

        with self.mock_datetime_and_now("2024-05-01"):
            validity_date = fields.Date.from_string('2024-05-05')
            archived_request = self.create_sign_request_no_item(
                signer=self.partner_1,
                cc_partners=self.partner_4,
                validity=validity_date
            )
            # This action should set the state to canceled.
            archived_request.action_archive()

            # Jump to the future and run the cron
            with self.mock_datetime_and_now("2024-05-06"):
                self.env['sign.request']._cron_reminder()
                self.assertTrue(archived_request.state == 'canceled')

    @users('admin')
    def test_sign_request_notification(self):
        """
        Test the sign request notification by creating a user with notification settings
        and checking if the notification type is set to 'inbox' in the created sign request.
        """
        self.env.user.write({
            'name': 'Mitchell Admin',
            'email': 'admin@example.com',
            'notification_type': 'inbox',
        })

        with self.mock_mail_gateway():
            # Create a sign request
            sign_request = self.env['sign.request'].create({
                'template_id': self.template_1_role.id,
                'reference': self.template_1_role.display_name,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_1.id,
                    'mail_sent_order': 1,
                })],
                'subject': 'Test Sign Request',
                'message': 'Please sign this document',
            })

            # Map the sign request items by role
            sign_request_items_by_role = {item.role_id: item for item in sign_request.request_item_ids}
            sign_request_item_signer_1 = sign_request_items_by_role[self.role_signer_1]

            # Ensure the sign request is created with the correct state
            self.assertEqual(sign_request.state, 'sent', 'The sign request should be in "sent" state initially')

            # Verify that an email was sent to the signer
            mail = self.env['mail.mail'].search([
                ('email_to', '=', formataddr((self.partner_1.name, self.partner_1.email)))
            ], limit=1)

            self.assertTrue(mail, 'The initial sign request email should have been sent to the signer_1')
            self.assertSentEmail('"Mitchell Admin" <admin@example.com>', self.partner_1)
            self.assertTrue(sign_request_item_signer_1.is_mail_sent, 'An email should be marked as sent for the signer_1')

            # Simulate signing the document
            sign_request_item_signer_1.sudo().sign(self.single_signer_sign_values)
            self.assertEqual(sign_request.state, 'signed', 'The sign request should be signed')

            completion_mail_to_user = self.env['mail.mail'].search([
                ('email_to', '=', formataddr((self.env.user.partner_id.name, self.env.user.partner_id.email))),
                ('subject', 'ilike', sign_request.reference),
            ])
            self.assertEqual(1, len(completion_mail_to_user), 'Completion email should be sent to the admin user')

            completion_mail_to_partner = self.env['mail.mail'].search([
                ('email_to', '=', formataddr((self.partner_1.name, self.partner_1.email)))
            ])
            self.assertEqual(
                2, len(completion_mail_to_partner),
                'Two emails should have been sent to the partner: the initial sign request and the completion email'
            )

    def test_check_state_for_download(self):
        """Test downloading a completed document for signed requests and validation for unsigned requests."""

        # Create sign request with 3 roles (signer_1, signer_2, signer_3, cc partners)
        sign_request_3_roles = self.create_sign_request_3_roles(
            signer_1=self.partner_1,
            signer_2=self.partner_2,
            signer_3=self.partner_3,
            cc_partners=self.partner_4
        )
        # Map role to corresponding sign request item using a dictionary comprehension
        role2sign_request_item = {
            sign_request_item.role_id: sign_request_item
            for sign_request_item in sign_request_3_roles.request_item_ids
        }
        # Retrieve individual sign request items for signer 1, 2, and 3
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]
        # Get template and sign item IDs
        template = sign_request_3_roles.template_id
        sign_item_ids = template.sign_item_ids.ids
        # Sign the customer sign request item
        sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # Assertions after signing the signer_1 sign request item
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_3_roles.state, 'sent', 'The sign request should be signed')
        self.assertEqual(template.sign_item_ids.ids, sign_item_ids, 'The original template should not be changed')
        self.assertEqual(
            len(sign_request_3_roles.sign_log_ids.filtered(
                lambda log: log.action == 'sign' and log.sign_request_item_id == sign_request_item_signer_1
            )),
            1, 'A log with action="sign" should be created'
        )
        # Sign the employee sign request item
        sign_request_item_signer_2.sign(
            self.create_sign_values(sign_request_3_roles.template_id.sign_item_ids, sign_request_item_signer_2.role_id.id)
        )
        # Assertions after signing the employee sign request item
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_3.state, 'sent', 'The sign.request.item should be sent')
        completed_document = sign_request_3_roles.get_sign_request_documents()
        self.assertIsNotNone(completed_document, 'The completed document should be available for download.')

    def test_remove_validity_date_of_sign_request(self):
        validity_date = fields.Date.to_date(fields.Date.today()) + timedelta(days=1)
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4, validity=validity_date)
        sign_request.validity = False
        self.assertEqual(sign_request.state, 'sent')

    def test_expired_shared_sign_requests_are_cleaned_up(self):
        """ Tests that the expired sign requests are cleaned when the autovacuum job is called """

        with freeze_time("2025-05-16"):
            shared_request = self.env["sign.request"].create({
                'template_id': self.template_1_role.id,
                'reference': self.template_1_role.display_name,
                'request_item_ids': [Command.create({
                    'role_id': self.role_signer_1.id,
                })],
                'state': 'shared',
                'validity': fields.Date.today() + relativedelta(days=3)
            })

        with freeze_time("2025-05-20"):
            with self.enter_registry_test_mode():
                autovacuum_job = self.env.ref('base.autovacuum_job')
                if autovacuum_job:
                    autovacuum_job.method_direct_trigger()
                    self.assertFalse(shared_request.exists(), "The template is not shared anymore.")

    def test_sign_request_item_value_cannot_be_changed_after_create(self):
        """ Tests that a constant sign item can be created but its value cannot be not modified """
        constant_sign_request = self.create_sign_request_with_constant_field(
            customer=self.partner_1,
            cc_partners=self.partner_4
        )

        role2sign_request_item = {
            sign_request_item.role_id: sign_request_item
            for sign_request_item in constant_sign_request.request_item_ids
        }

        sign_request_item_customer = role2sign_request_item[self.role_1]

        with self.assertRaisesRegex(UserError, "Cannot update the value of a read-only sign item"):
            sign_request_item_customer.sign(self.create_sign_values(constant_sign_request.template_id.sign_item_ids, sign_request_item_customer.role_id.id))

    def test_send_reminder_without_set_validity(self):
        with self.mock_datetime_and_now("2025-07-06"):
            sign_request = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
            sign_request.write({'validity': None, 'reminder_enabled': True, 'reminder': 1})

        with self.mock_datetime_and_now("2025-07-07"):
            self.env['sign.request']._cron_reminder()

    def test_signing_order(self):
        wizard = Form(
            self.env['sign.send.request'].with_context(
                default_template_id=self.template_3_roles.id,
                sign_directly_without_mail=False,
            )
        )
        wizard.set_sign_order = True
        self.assertEqual(
            [record['mail_sent_order'] for record in wizard.signer_ids._records],
            [1, 2, 3],
        )
        request = wizard.save()
        request.signer_ids[0].mail_sent_order = 3
        request.signer_ids[1].mail_sent_order = 2
        request.signer_ids[2].mail_sent_order = 1
        wizard = Form(request)
        wizard.save()
        self.assertEqual(
            [s.mail_sent_order for s in request.signer_ids],
            [3, 2, 1],
        )

    def test_run_action_sign_multi(self):
        """ Test creating a sign request with two signers from the server action. """
        roles = self.template_2_roles.sign_item_ids.responsible_id.sorted('id')
        roles[0].sign_action_partner_id = self.partner_1
        roles[1].sign_action_partner_id = self.partner_2
        action = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'name': 'Test Sign Action',
            'state': 'sign',
            'sign_template_id': self.template_2_roles.id,
        })
        test_record = self.env['res.partner'].create({'name': 'Test Partner', 'email': 'test@example.com'})
        eval_context = {'model': 'res.partner', 'record': test_record, 'records': test_record}
        action._run_action_sign_multi(eval_context=eval_context)

        sign_request = self.env['sign.request'].search([('template_id', '=', self.template_2_roles.id)], order='id desc', limit=1)
        self.assertTrue(sign_request, 'Sign request should be created.')
        self.assertEqual(len(sign_request.request_item_ids), 2, 'Sign request should have two signers.')
        sorted_items = sign_request.request_item_ids.sorted('mail_sent_order')
        self.assertEqual(sorted_items[0].partner_id, self.partner_1, 'First signer should match.')
        self.assertEqual(sorted_items[1].partner_id, self.partner_2, 'Second signer should match.')
        self.assertEqual(sorted_items[0].role_id, roles[0], 'First signer role should match.')
        self.assertEqual(sorted_items[1].role_id, roles[1], 'Second signer role should match.')

    def test_run_action_sign_multi_linked_field(self):
        """ Test creating a sign request using linked field signers. """
        test_user_1 = self.env['res.users'].create({'name': 'Test User 1', 'login': 'test_user_1', 'email': 'test1@example.com'})
        test_user_2 = self.env['res.users'].create({'name': 'Test User 2', 'login': 'test_user_2', 'email': 'test2@example.com'})
        roles = self.template_2_roles.sign_item_ids.responsible_id.sorted('id')
        field_create_uid = self.env['ir.model.fields'].search([('model', '=', 'res.partner'), ('name', '=', 'create_uid')], limit=1)
        field_write_uid = self.env['ir.model.fields'].search([('model', '=', 'res.partner'), ('name', '=', 'write_uid')], limit=1)
        roles[0].signer_type = 'linked_field'
        roles[0].linked_field_id = field_create_uid
        roles[1].signer_type = 'linked_field'
        roles[1].linked_field_id = field_write_uid
        action = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'name': 'Test Sign Action with Linked Fields',
            'state': 'sign',
            'sign_template_id': self.template_2_roles.id,
        })
        test_record = self.env['res.partner'].create({'name': 'Test Partner', 'email': 'test@example.com'})
        test_record.write({'create_uid': test_user_1.id, 'write_uid': test_user_2.id})
        eval_context = {'model': 'res.partner', 'record': test_record, 'records': test_record}
        action._run_action_sign_multi(eval_context=eval_context)

        sign_request = self.env['sign.request'].search([('template_id', '=', self.template_2_roles.id)], order='id desc', limit=1)
        self.assertTrue(sign_request, 'Sign request should be created.')
        self.assertEqual(len(sign_request.request_item_ids), 2, 'Sign request should have two signers.')
        sorted_items = sign_request.request_item_ids.sorted('mail_sent_order')
        self.assertEqual(sorted_items[0].partner_id, test_user_1.partner_id, 'First signer should be from create_uid.')
        self.assertEqual(sorted_items[1].partner_id, test_user_2.partner_id, 'Second signer should be from write_uid.')

    def test_sign_action_signer_persistence(self):
        """ Signer settings should persist on roles even if transient records are cleared. """
        roles = self.template_2_roles.sign_item_ids.responsible_id.sorted('id')
        field_create_uid = self.env['ir.model.fields'].search([('model', '=', 'res.partner'), ('name', '=', 'create_uid')], limit=1)
        roles.write({
            'signer_type': 'fixed',
            'sign_action_partner_id': self.partner_1.id
        })
        action = self.env['ir.actions.server'].create({
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'name': 'Persistent Sign Action',
            'state': 'sign',
            'sign_template_id': self.template_2_roles.id,
        })
        signer = action.sign_role_ids.filtered(lambda s: s == roles[0])
        signer.ensure_one()

        signer.write({'signer_type': 'linked_field', 'linked_field_id': field_create_uid.id, 'sign_action_partner_id': self.partner_1.id})
        self.assertEqual(roles[0].signer_type, 'linked_field', 'Signer type should be linked_field.')
        self.assertEqual(roles[0].linked_field_id, field_create_uid, 'Linked field should match.')
        self.assertEqual(roles[0].sign_action_partner_id, self.partner_1, 'Partner should match.')

    def test_sign_server_action_template_conflict(self):
        """ Selecting a template already linked to another action should raise an error. """
        model_id = self.env['ir.model']._get('res.partner')
        roles = self.template_2_roles.sign_item_ids.responsible_id
        roles.write({
            'signer_type': 'fixed',
            'sign_action_partner_id': self.partner_1.id
        })
        with Form(self.env['ir.actions.server']) as action_form:
            action_form.model_id = model_id
            action_form.name = 'Sign Action 1'
            action_form.state = 'sign'
            action_form.sign_template_id = self.template_2_roles
            action_form.save()

        with self.assertRaisesRegex(ValidationError, "The sign roles of the template that you are selecting"):
            with Form(self.env['ir.actions.server']) as action_form2:
                action_form2.model_id = model_id
                action_form2.name = 'Sign Action 2'
                action_form2.state = 'sign'
                action_form2.sign_template_id = self.template_2_roles
                action_form2.save()

    def test_sign_server_action_template_switch_clears_roles(self):
        """ Switching templates should clear role links on the previous template. """
        model_id = self.env['ir.model']._get('res.partner')
        old_roles = self.template_2_roles.sign_item_ids.responsible_id
        new_roles = self.template_3_roles.sign_item_ids.responsible_id
        (old_roles | new_roles).write({
            'signer_type': 'fixed',
            'sign_action_partner_id': self.partner_1.id
        })
        with Form(self.env['ir.actions.server']) as action_form:
            action_form.model_id = model_id
            action_form.name = 'Sign Action Switch'
            action_form.state = 'sign'
            action_form.sign_template_id = self.template_2_roles
            action = action_form.save()
        with Form(action) as action_form:
            action_form.sign_template_id = self.template_3_roles
            action_form.save()
        self.env.flush_all()
        action.invalidate_recordset()

        exclusive_old_roles = old_roles - new_roles
        self.assertTrue(all(not role.ir_actions_server_id for role in exclusive_old_roles), 'Old exclusive roles should be cleared.')
        self.assertTrue(all(role.ir_actions_server_id == action for role in new_roles), 'New roles should be linked to action.')

    def test_sign_server_action_unlink_clears_roles(self):
        """ Deleting an action should clear the linked role settings. """
        model_id = self.env['ir.model']._get('res.partner')
        roles = self.template_2_roles.sign_item_ids.responsible_id
        roles.write({
            'signer_type': 'fixed',
            'sign_action_partner_id': self.partner_1.id
        })
        with Form(self.env['ir.actions.server']) as action_form:
            action_form.model_id = model_id
            action_form.name = 'Sign Action Unlink'
            action_form.state = 'sign'
            action_form.sign_template_id = self.template_2_roles
            action = action_form.save()
        roles = self.template_2_roles.sign_item_ids.responsible_id
        self.assertTrue(any(role.ir_actions_server_id == action for role in roles), 'Roles should be linked to action.')
        action.unlink()
        self.env.flush_all()

        for role in roles:
            role.invalidate_recordset()
        self.assertTrue(all(not role.ir_actions_server_id for role in roles), 'Roles should be cleared after action unlink.')

    def test_sign_server_action_model_change_resets_linked_field(self):
        """ Changing model_id should reset linked_field_id for all roles. """
        partner_model = self.env['ir.model']._get('res.partner')
        user_model = self.env['ir.model']._get('res.users')
        partner_field = self.env['ir.model.fields'].search([('model', '=', 'res.partner'), ('name', '=', 'create_uid')], limit=1)
        roles = self.template_2_roles.sign_item_ids.responsible_id
        roles.write({
            'signer_type': 'fixed',
            'sign_action_partner_id': self.partner_1.id
        })
        action = self.env['ir.actions.server'].create({
            'model_id': partner_model.id,
            'name': 'Test Model Change',
            'state': 'sign',
            'sign_template_id': self.template_2_roles.id,
        })
        role = self.template_2_roles.sign_item_ids.responsible_id[0]
        role.write({'signer_type': 'linked_field', 'linked_field_id': partner_field.id})
        self.assertTrue(role.linked_field_id, 'linked_field_id should be set.')

        with Form(action) as form:
            form.model_id = user_model
        form.save()

        self.assertFalse(role.linked_field_id, 'linked_field_id should be cleared when model_id changes.')

    def test_constant_required_field_preserves_empty_auto_field_value(self):
        """ Test that empty auto-filled values are preserved for constant required fields. """
        # Create a custom sign item type with model_id, auto_field, placeholder, constant and required.
        partner_model = self.env['ir.model']._get('res.partner')
        custom_item_type = self.env['sign.item.type'].create({
            'name': 'Test Company Registration',
            'item_type': 'text',
            'model_id': partner_model.id,
            'auto_field': 'ref',  # Field that may not have a value.
            'placeholder': 'Company Registration Number',
            'constant': True,
            'required': True,
        })

        # Create a template with the custom item type, then create a sign item with the custom type.
        template = self.env['sign.template'].create({'name': 'Template with Constant Required Field'})
        document = self.env['sign.document'].create({'attachment_id': self.attachment.id, 'template_id': template.id})
        sign_item = self.env['sign.item'].create({
            'type_id': custom_item_type.id, 'required': True, 'constant': True,
            'responsible_id': self.role_signer_1.id, 'page': 1, 'posX': 0.273,
            'posY': 0.158, 'document_id': document.id, 'width': 0.150, 'height': 0.015,
        })

        # Ensure partner_1 has no ref value.
        self.partner_1.ref = False

        # Create a sign request
        sign_request = self.env['sign.request'].create({
            'template_id': template.id,
            'reference': template.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.role_signer_1.id,
            })],
        })
        sign_request_item = sign_request.request_item_ids[0]

        # Since the field is constant and required, it should not be in the required_ids set and should not need to be signed by the user.
        sign_request._populate_constant_items()
        sign_request_item.sudo().sign(signature={})

        # Check that the sign request item has been completed.
        self.assertEqual(sign_request_item.state, 'completed', 'Sign request item should be completed.')
        self.assertEqual(sign_request.state, 'signed', 'Sign request should be signed.')

        # Verify that the constant field value was created with the placeholder.
        item_value = self.env['sign.request.item.value'].search([
            ('sign_request_item_id', '=', sign_request_item.id),
            ('sign_item_id', '=', sign_item.id),
        ])

        self.assertTrue(item_value, 'A sign item value should be created for the constant field.')
        self.assertFalse(item_value.value, 'The empty auto field value should be preserved.')

    def test_custom_field_autofill(self):
        """ Test that custom sign item types are auto-filled with previous values from the same signer. """
        custom_type = self.env['sign.item.type'].create({'name': 'Custom Field', 'item_type': 'text'})
        template = self.env['sign.template'].create({'name': 'Template Custom'})
        document = self.env['sign.document'].create({'attachment_id': self.attachment.id, 'template_id': template.id})
        self.env['sign.item'].create({
            'type_id': custom_type.id, 'required': True, 'responsible_id': self.role_signer_1.id,
            'page': 1, 'posX': 0.273, 'posY': 0.158, 'document_id': document.id, 'width': 0.150, 'height': 0.015,
        })
        sr1 = self.env['sign.request'].create({
            'template_id': template.id, 'reference': 'Test Custom 1',
            'request_item_ids': [Command.create({'partner_id': self.partner_1.id, 'role_id': self.role_signer_1.id})],
        })
        sr1.request_item_ids._fill({str(document.sign_item_ids[0].id): "CustomValue123"})
        sr1.request_item_ids._post_fill_request_item()
        sr2 = self.env['sign.request'].create({
            'template_id': template.id, 'reference': 'Test Custom 2',
            'request_item_ids': [Command.create({'partner_id': self.partner_1.id, 'role_id': self.role_signer_1.id})],
        })
        auto_value = sr2.request_item_ids._get_auto_field_value({'id': custom_type.id, 'auto_field': False})
        self.assertEqual(auto_value, "CustomValue123", 'Custom field should auto-fill with previous value')

    def test_sign_request_alias_email_raises_user_error(self):
        """ Ensure that signing with a system alias email must raise an UserError. """
        self.env['mail.alias.domain'].create({'name': 'alias.example.com', 'catchall_alias': 'catchall'})
        alias_partner = self.env['res.partner'].create({'name': 'Alias Partner', 'email': 'catchall@alias.example.com'})
        with self.assertRaises(UserError):
            self.create_sign_request_1_role(signer=alias_partner, cc_partners=self.env['res.partner'])

    def test_sign_request_cancel_signed_document(self):
        """ Ensure that a fully signed document cannot be canceled. """
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        sign_request_item = sign_request.request_item_ids[0]

        # Sign the document.
        sign_request_item.sign(self.signature_fake)
        self.assertEqual(sign_request.state, 'signed', 'The sign request should be signed.')

        # Attempt to cancel, document should remain signed.
        sign_request.cancel()
        self.assertEqual(sign_request.state, 'signed', 'A fully signed document should not be canceled.')

    def test_sign_server_action_required_signers_constraints(self):
        """ Ensure that required fields for signature roles are strictly enforced. """
        model_id = self.env['ir.model']._get_id('res.partner')
        roles = self.template_2_roles.sign_item_ids.responsible_id
        roles.write({
            'signer_type': 'fixed',
            'sign_action_partner_id': False  # Intentionally left blank
        })
        with self.assertRaisesRegex(ValidationError, "Please specify a Fixed Signer"):
            self.env['ir.actions.server'].create({
                'model_id': model_id,
                'name': 'Failing Action 1',
                'state': 'sign',
                'sign_template_id': self.template_2_roles.id,
                'sign_role_ids': [Command.set(roles.ids)],
            })

        roles.write({
            'signer_type': 'linked_field',
            'linked_field_id': False  # Intentionally left blank
        })
        with self.assertRaisesRegex(ValidationError, "Please specify a Linked Field"):
            self.env['ir.actions.server'].create({
                'model_id': model_id,
                'name': 'Failing Action 2',
                'state': 'sign',
                'sign_template_id': self.template_2_roles.id,
                'sign_role_ids': [Command.set(roles.ids)],
            })

        roles.write({
            'signer_type': 'fixed',
            'sign_action_partner_id': self.partner_1.id
        })
        valid_action = self.env['ir.actions.server'].create({
            'model_id': model_id,
            'name': 'Passing Action',
            'state': 'sign',
            'sign_template_id': self.template_2_roles.id,
            'sign_role_ids': [Command.set(roles.ids)],
        })
        self.assertTrue(valid_action.id, "The action should successfully save with valid roles.")

    def test_sign_request_auto_update(self):
        res = self.env['sign.template'].create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'raw': self.pdf_value}]
        )
        sign_template_id = res.get('id', 0)
        sign_template = self.env['sign.template'].browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        partner_id = self.env["res.partner"].create({
            'name': 'original name',
            'email': 'original@example.com',
        })
        type_name = self.env["sign.item.type"].create({
            'name': 'update name',
            'item_type': 'text',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'auto_field': 'name',
            'auto_write': True
        })
        type_email = self.env["sign.item.type"].create({
            'name': 'update email',
            'item_type': 'text',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'auto_field': 'email',
            'auto_write': True
        })
        item_name = self.env["sign.item"].create({
            'template_id': sign_template_id,
            'document_id': document_id,
            'type_id': type_name.id,
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.1, 'width': 0.1, 'height': 0.01,
        })
        item_email = self.env["sign.item"].create({
            'template_id': sign_template_id,
            'document_id': document_id,
            'type_id': type_email.id,
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.2, 'width': 0.1, 'height': 0.01,
        })
        sign_request = self.env['sign.request'].create({
            'template_id': sign_template_id,
            'request_item_ids': [Command.create({
                'partner_id': partner_id.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
            'reference': 'test multiple auto-update',
            'reference_doc': f'res.partner,{partner_id.id}',
        })
        sign_request_item = sign_request.request_item_ids[0]

        sign_request_item.with_user(self.env.ref('base.public_user')).sudo().sign({
            str(item_name.id): 'New Name',
            str(item_email.id): 'new@example.com',
        })
        self.assertEqual(partner_id.name, 'New Name')
        self.assertEqual(partner_id.email, 'new@example.com')

    def test_sign_request_auto_update_conflict(self):
        res = self.env['sign.template'].create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'raw': self.pdf_value}]
        )
        sign_template_id = res['id']
        sign_template = self.env['sign.template'].browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        partner_id = self.env["res.partner"].create({
            'name': 'original',
            'email': 'partner@gmail.com',
        })

        type_id = self.env["sign.item.type"].create({
            'name': 'update name conflict',
            'item_type': 'text',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'auto_field': 'name',
            'auto_write': True
        })
        item1 = self.env["sign.item"].create({
            'template_id': sign_template_id, 'document_id': document_id, 'type_id': type_id.id,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.1, 'width': 0.1, 'height': 0.01,
        })
        item2 = self.env["sign.item"].create({
            'template_id': sign_template_id, 'document_id': document_id, 'type_id': type_id.id,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.2, 'width': 0.1, 'height': 0.01,
        })
        sign_request = self.env['sign.request'].create({
            'template_id': sign_template_id,
            'request_item_ids': [Command.create({
                'partner_id': partner_id.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
            'reference': 'test conflict',
            'reference_doc': f'res.partner,{partner_id.id}',
        })
        sign_request_item = sign_request.request_item_ids[0]

        sign_request_item.with_user(self.env.ref('base.public_user')).sudo().sign({
            str(item1.id): 'Value A',
            str(item2.id): 'Value B',
        })
        self.assertEqual(partner_id.name, 'original')

        sign_request2 = sign_request.copy()
        sign_request2.reference_doc = f'res.partner,{partner_id.id}'
        sign_request_item2 = sign_request2.request_item_ids[0]

        sign_request_item2.with_user(self.env.ref('base.public_user')).sudo().sign({
            str(item1.id): 'Identical',
            str(item2.id): 'Identical',
        })
        self.assertEqual(partner_id.name, 'Identical')

    def test_sign_request_auto_update_nested_field(self):
        res = self.env['sign.template'].create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'raw': self.pdf_value}]
        )
        sign_template_id = res['id']
        sign_template = self.env['sign.template'].browse(sign_template_id)
        document_id = sign_template.document_ids[0].id

        parent_partner = self.env['res.partner'].create({'name': 'Parent Company', 'is_company': True})
        child_partner = self.env['res.partner'].create({
            'name': 'Child Partner',
            'parent_id': parent_partner.id,
            'email': 'partner@gmail.com',
        })

        type_parent_name = self.env['sign.item.type'].create({
            'name': 'update parent name',
            'item_type': 'text',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'auto_field': 'parent_id.name',
            'auto_write': True
        })

        item = self.env['sign.item'].create({
            'template_id': sign_template_id, 'document_id': document_id, 'type_id': type_parent_name.id,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.1, 'width': 0.1, 'height': 0.01,
        })

        sign_request = self.env['sign.request'].create({
            'template_id': sign_template_id,
            'request_item_ids': [Command.create({
                'partner_id': child_partner.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
            'reference': 'test nested auto-update',
            'reference_doc': f'res.partner,{child_partner.id}',
        })

        sign_request_item = sign_request.request_item_ids[0]
        sign_request_item.with_user(self.env.ref('base.public_user')).sudo().sign({
            str(item.id): 'New Parent Name',
        })

        self.assertEqual(parent_partner.name, 'New Parent Name')

    def test_sign_request_auto_update_permission_error(self):
        res = self.env['sign.template'].create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'raw': self.pdf_value}]
        )
        sign_template_id = res['id']
        sign_template = self.env['sign.template'].browse(sign_template_id)
        document_id = sign_template.document_ids[0].id

        target_record = self.env['res.partner'].create({'name': 'Protected Vault'})
        original_name = target_record.name

        type_id = self.env['sign.item.type'].create({
            'name': 'update permission check',
            'item_type': 'text',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'auto_field': 'name',
            'auto_write': True
        })

        item = self.env['sign.item'].create({
            'template_id': sign_template_id, 'document_id': document_id, 'type_id': type_id.id,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.1, 'width': 0.1, 'height': 0.01,
        })

        # User has Sign User rights but not partner writing rights
        user_no_rights = new_test_user(self.env, login='test_user_no_rights', groups='sign.group_sign_user')
        sign_template.write({
            'authorized_ids': [Command.link(user_no_rights.id)]
        })

        sign_request = self.env['sign.request'].with_user(user_no_rights).create({
            'template_id': sign_template_id,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
            'reference': 'test permission failure',
            'reference_doc': f'res.partner,{target_record.id}',
        })

        sign_request_item = sign_request.request_item_ids[0]
        # The signing is sudo, but write-back uses the request sender's (user_no_rights) permissions
        with self.assertLogs('odoo.addons.sign.models.sign_request', level='WARNING') as captured_logs:
            sign_request_item.with_user(self.env.ref('base.public_user')).sudo().sign({
                str(item.id): 'Should Fail',
            })

        self.assertTrue(
            any('Sign Sync: Failed to update auto-fields' in log for log in captured_logs.output),
            "The expected permission warning was not triggered!"
        )

        self.assertEqual(target_record.name, original_name)  # Name should not have changed

    def test_sign_server_action_batch_template_conflict(self):
        """ Batch creating multiple actions using the same template roles should raise an error. """
        model_id = self.env['ir.model']._get_id('res.partner')
        with self.assertRaisesRegex(ValidationError, "You are trying to save multiple actions"):
            self.env['ir.actions.server'].create([
                {
                    'model_id': model_id,
                    'name': 'Batch Sign Action 1',
                    'state': 'sign',
                    'sign_template_id': self.template_2_roles.id,
                },
                {
                    'model_id': model_id,
                    'name': 'Batch Sign Action 2',
                    'state': 'sign',
                    'sign_template_id': self.template_2_roles.id,
                }
            ])

    @users('admin')
    def test_search_need_my_signature(self):
        self.env.user.email = "admin@test.com"
        sign_request_1 = self.create_sign_request_no_item(signer=self.env.user.partner_id, cc_partners=self.partner_4)
        sign_request_2 = self.create_sign_request_no_item(signer=self.partner_2, cc_partners=self.partner_4)

        # Search for documents waiting for admin
        waiting_for_me = self.env['sign.request'].search([('need_my_signature', '=', True)]).ids
        self.assertIn(sign_request_1.id, waiting_for_me, "Document where admin is a signer should be in 'Waiting for me'")
        self.assertNotIn(sign_request_2.id, waiting_for_me, "Document where admin is NOT a signer should NOT be in 'Waiting for me'")

    def test_sign_activity_not_visible_without_sign_access(self):
        """ Check no access error when displaying a sign request activity in the
        chatter of a record the user has access to, if they don't have access to
        the `sign_request_id` of the activity. """

        sign_request = self.create_sign_request_1_role(self.partner_1, self.partner_1)

        activity = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'res_id': self.partner_1.id,
            'activity_type_id': self.env.ref('sign.mail_activity_data_signature_request').id,
            'sign_request_id': sign_request.id,
        })

        sign_request.invalidate_recordset()
        self.assertFalse(sign_request.with_user(self.user_5).has_access('read'))
        self.assertTrue(self.partner_1.with_user(self.user_5).has_access('read'))

        Store().add(activity.with_user(self.user_5), "_store_activity_fields")._build_result()  # simulates chatter display
        self.assertFalse(activity.with_user(self.user_5).can_write)

    def test_origin_offset_translation(self):
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        reader = PdfFileReader(io.BytesIO(sign_request.template_document_ids.attachment_id.raw), strict=False)
        reader.pages[0].cropbox.lower_left = (-1000, -1000)
        writer = PdfFileWriter()
        writer.add_page(reader.pages[0])
        out_buffer = io.BytesIO()
        writer.write(out_buffer)
        sign_request.template_document_ids.attachment_id.raw = out_buffer.getvalue()
        sign_request.write({'state': 'signed'})
        with patch.object(canvas.Canvas, 'translate') as mock_translate:
            sign_request.template_document_ids.render_document_with_items()
            self.assertTrue(mock_translate.called, "The origin offset was ignored.")
            args = mock_translate.call_args[0]
            self.assertEqual(args[0], -1000)
            self.assertEqual(args[1], -1000)


class TestSignRequestHTTP(TestSignRequest, HttpCaseWithUserDemo):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Add the Sign / User: Own Templates to demo so he is able to create templates and send signature requests
        cls.user_demo.group_ids += cls.env.ref("sign.group_sign_user")
        # Create as admin to be able to set the `auto_field`
        # You do not have enough rights to access the field "auto_field" on Signature Item Type (sign.item.type)
        # Groups: allowed for groups 'Role / Administrator'
        cls.type_email = cls.env["sign.item.type"].create({
            'name': 'update email',
            'item_type': 'text',
            'model_id': cls.env['ir.model']._get_id('res.partner'),
            'auto_field': 'email',
            'auto_write': True,
            'shared': True,
        })

    @users("demo")
    def test_sign_request_auto_update_different_partner(self):
        admin_email = self.partner_admin.email = "admin@odoo.com"
        attacker_email = "attacker@example.com"

        res = self.env['sign.template'].create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'raw': self.pdf_value}]
        )
        sign_template_id = res.get('id', 0)
        sign_template = self.env['sign.template'].browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        item_email = self.env["sign.item"].create({
            'template_id': sign_template_id,
            'document_id': document_id,
            'type_id': self.type_email.id,
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1, 'posX': 0.1, 'posY': 0.2, 'width': 0.1, 'height': 0.01,
        })
        sign_request = self.env['sign.request'].create({
            'template_id': sign_template_id,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_admin.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
            'reference': 'test multiple auto-update',
            'reference_doc': f'res.partner,{self.partner_admin.id}',
        })
        sign_request_item = sign_request.request_item_ids[0]

        before_messages = sign_request.message_ids

        with self.assertLogs("odoo.addons.sign.models.sign_request") as log_catcher_sign_request:
            self.url_open(f"/sign/sign/{sign_request.id}/{sign_request_item.sudo().access_token}", json={"params": {
                'signature': {item_email.id: attacker_email}
            }})

        # Expected logs
        self.assertIn(f"Failed to update auto-fields on {self.partner_admin!r}", log_catcher_sign_request.output[0])
        self.assertIn("doesn't have 'write' access to:\n- User", log_catcher_sign_request.output[0])

        # The email of the admin should remain unchanged
        self.assertEqual(self.partner_admin.email, admin_email)
        self.assertNotEqual(self.partner_admin.email, attacker_email)

        # Expected messages:
        #  - a message telling the auto update failed must be present,
        #  - and the one confirming fields were auto-updated must not
        new_messages = sign_request.message_ids - before_messages
        self.assertEqual(
            len(new_messages),
            4,
            """
                4 messages expected:
                 - Auto-update blocked,
                 - To sign -> signed,
                 - mail has been sent to contacts in copy,
                 - request signature done
            """
        )

        self.assertTrue(new_messages.filtered(
            lambda m: "Auto-update blocked: request sender lacks permission to update" in m.body
        ))
