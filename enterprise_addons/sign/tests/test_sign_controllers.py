# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch
from freezegun import freeze_time
from json import dumps

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.http_routing.tests.common import MockRequest
from odoo.addons.mail.tests.common import MockEmail
from odoo.tests import tagged
from odoo.tools import formataddr
from .sign_controller_common import TestSignControllerCommon

@tagged('post_install', '-at_install')
class TestSignController(TestSignControllerCommon, MockEmail):
    # test float auto_field display
    def test_sign_controller_float(self):
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        self.partner_1.partner_latitude = 45.154515254521
        text_type = self.env['sign.item.type'].search([('name', '=', 'Text')])
        # the partner_latitude expects 7 zeros of decimal precision
        text_type.auto_field = 'partner_latitude'
        text_type.model_id = self.env['ir.model']._get('res.partner').id
        token_a = self.env["sign.request.item"].search([('sign_request_id', '=', sign_request.id)]).access_token
        with MockRequest(sign_request.env):
            values = self.SignController.get_document_qweb_context(sign_request.id, token=token_a)
            sign_type = next(filter(lambda sign_type: sign_type["name"] == "Text", values.get("rendering_context")["sign_item_types"]))
            latitude = sign_type["auto_value"]
            #  floats are rounded
            self.assertEqual(latitude, 45.15)

    # test auto_field with wrong partner field
    def test_sign_controller_dummy_fields(self):
        text_type = self.env['sign.item.type'].search([('name', '=', 'Text')])
        # we set a dummy field that raises an error
        text_type.model_id = self.env['ir.model']._get('res.partner').id
        with self.assertRaises(ValidationError):
            text_type.auto_field = 'this_is_not_a_partner_field'

        # we set a field the demo user does not have access and must not be able to set as auto_field
        self.patch(type(self.env['res.partner']).function, 'groups', 'base.group_system')
        with self.assertRaises(AccessError):
            text_type.with_user(self.user_demo).auto_field = 'function'

    # test auto_field with multiple sub steps
    def test_sign_controller_multi_step_auto_field(self):
        self.partner_1.company_id = self.env.ref('base.main_company')
        self.partner_1.company_id.country_id = self.env.ref('base.be').id
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        text_type = self.env['sign.item.type'].search([('name', '=', 'Text')])
        text_type.model_id = self.env['ir.model']._get('res.partner').id
        text_type.auto_field = 'company_id.country_id.name'
        token_a = self.env["sign.request.item"].search([('sign_request_id', '=', sign_request.id)]).access_token
        with MockRequest(sign_request.env):
            values = self.SignController.get_document_qweb_context(sign_request.id, token=token_a)
            sign_type = next(filter(lambda sign_type: sign_type["name"] == "Text", values.get("rendering_context")["sign_item_types"]))
            country = sign_type["auto_value"]
            self.assertEqual(country, "Belgium")
        # test falsy value
        self.env.ref('base.be').phone_code = 0
        text_type.auto_field = 'company_id.country_id.phone_code'
        sign_request2 = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        token_b = self.env["sign.request.item"].search([('sign_request_id', '=', sign_request2.id)]).access_token
        with MockRequest(sign_request.env):
            values = self.SignController.get_document_qweb_context(sign_request2.id, token=token_b)
            sign_type = next(filter(lambda sign_type: sign_type["name"] == "Text", values.get("rendering_context")["sign_item_types"]))
            phone_code = sign_type["auto_value"]
            self.assertTrue(phone_code == 0)
        text_type.auto_field = 'company_id.country_id.address_view_id.technical_usage'
        sign_request2 = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        token_b = self.env["sign.request.item"].search([('sign_request_id', '=', sign_request2.id)]).access_token
        with MockRequest(sign_request.env):
            values = self.SignController.get_document_qweb_context(sign_request2.id, token=token_b)
            sign_type = next(filter(lambda sign_type: sign_type["name"] == "Text", values.get("rendering_context")["sign_item_types"]))
            technical_usage = sign_type["auto_value"]
            self.assertEqual(technical_usage, "")

    def test_sign_request_requires_auth_when_credits_are_available(self):
        sign_request = self.create_sign_request_1_role_sms_auth(self.partner_1, self.env['res.partner'])
        sign_request_item = sign_request.request_item_ids[0]

        self.assertFalse(sign_request_item.signed_without_extra_auth)
        self.assertEqual(sign_request_item.role_id.auth_method, 'sms')

        sign_vals = self.create_sign_values(sign_request.template_id.sign_item_ids, sign_request_item.role_id.id)
        with patch('odoo.addons.iap.models.iap_account.IapAccount.get_credits', lambda self, x: 10):
            response = self._json_url_open(
                '/sign/sign/%d/%s' % (sign_request.id, sign_request_item.access_token),
                data={'signature': sign_vals}
            ).json()['result']

            self.assertFalse(response.get('success'))
            self.assertTrue(sign_request_item.state, 'sent')
            self.assertFalse(sign_request_item.signed_without_extra_auth)

    def test_sign_request_allows_no_auth_when_credits_are_not_available(self):
        sign_request = self.create_sign_request_1_role_sms_auth(self.partner_1, self.env['res.partner'])
        sign_request_item = sign_request.request_item_ids[0]

        self.assertFalse(sign_request_item.signed_without_extra_auth)
        self.assertEqual(sign_request_item.role_id.auth_method, 'sms')

        sign_vals = self.create_sign_values(sign_request.template_id.sign_item_ids, sign_request_item.role_id.id)
        with patch('odoo.addons.iap.models.iap_account.IapAccount.get_credits', lambda self, x: 0):
            response = self._json_url_open(
                '/sign/sign/%d/%s' % (sign_request.id, sign_request_item.access_token),
                data={'signature': sign_vals}
            ).json()['result']

            self.assertTrue(response.get('success'))
            self.assertTrue(sign_request_item.state, 'completed')
            self.assertTrue(sign_request.state, 'done')
            self.assertTrue(sign_request_item.signed_without_extra_auth)

    def test_sign_from_mail_no_expiry_params(self):
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        url = '/sign/document/mail/%s/%s' % (sign_request.id, sign_request.request_item_ids[0].access_token)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue('The signature request might have been deleted or modified.' in response.text)

    def test_sign_from_mail_link_not_expired(self):
        with freeze_time('2020-01-01'):
            sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
            sign_request_item_id = sign_request.request_item_ids[0]
            timestamp = sign_request_item_id._generate_expiry_link_timestamp()
            expiry_hash = sign_request_item_id._generate_expiry_signature(sign_request_item_id.id, timestamp)

            url = '/sign/document/mail/%(sign_request_id)s/%(access_token)s?timestamp=%(timestamp)s&exp=%(exp)s' % {
                'sign_request_id': sign_request.id,
                'access_token': sign_request.request_item_ids[0].access_token,
                'timestamp': timestamp,
                'exp': expiry_hash
            }
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue('/sign/document/%s/%s' % (sign_request.id, sign_request_item_id.access_token) in response.url)

    def test_sign_from_mail_with_expired_link(self):
        with freeze_time('2020-01-01'):
            sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
            sign_request_item_id = sign_request.request_item_ids[0]
            timestamp = sign_request_item_id._generate_expiry_link_timestamp()
            expiry_hash = sign_request_item_id._generate_expiry_signature(sign_request_item_id.id, timestamp)

        with freeze_time('2020-01-17'):
            url = '/sign/document/mail/%(sign_request_id)s/%(access_token)s?timestamp=%(timestamp)s&exp=%(exp)s' % {
                'sign_request_id': sign_request.id,
                'access_token': sign_request.request_item_ids[0].access_token,
                'timestamp': timestamp,
                'exp': expiry_hash
            }
            response = self.url_open(url)
            self.assertEqual(response.status_code, 403)
            self.assertTrue('This link has expired' in response.text)

    def test_shared_sign_request_without_expiry_params(self):
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        sign_request.state = 'shared'
        sign_request_item_id = sign_request.request_item_ids[0]
        url = '/sign/document/mail/%s/%s' % (sign_request.id, sign_request_item_id.access_token)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('/sign/document/%s/%s' % (sign_request.id, sign_request_item_id.access_token) in response.url)

    def test_sign_from_resend_expired_link(self):
        with freeze_time('2020-01-01'):
            sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
            sign_request_item_id = sign_request.request_item_ids[0]
            timestamp = sign_request_item_id._generate_expiry_link_timestamp()
            expiry_hash = sign_request_item_id._generate_expiry_signature(sign_request_item_id.id, timestamp)

            url = '/sign/document/mail/%(sign_request_id)s/%(access_token)s?timestamp=%(timestamp)s&exp=%(exp)s' % {
                'sign_request_id': sign_request.id,
                'access_token': sign_request.request_item_ids[0].access_token,
                'timestamp': timestamp,
                'exp': expiry_hash
            }
            response = self.url_open(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue('/sign/document/%s/%s' % (sign_request.id, sign_request_item_id.access_token) in response.url)

            sign_request_item = {sign_request_item.role_id: sign_request_item for sign_request_item in sign_request.request_item_ids}
            sign_request_item_signer_1 = sign_request_item[self.role_signer_1]

            sign_request_item_signer_1.sudo().sign(self.single_signer_sign_values)
            mail = self.env['mail.mail'].search([('email_to', '=', formataddr((self.partner_1.name, self.partner_1.email)))])
            self.assertEqual(len(mail.ids), 2)

        with freeze_time('2020-01-17'):
            self.start_tour(url, 'sign_resend_expired_link_tour', login='demo')

    def test_cancel_request_as_public_user(self):
        """
        Test that a public user can cancel a sign request and that a cancellation log is recorded on the partner_id.
        """
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        sign_request_item = sign_request.request_item_ids[0]

        data = {
            'params': {
                'refusal_reason': 'No.',
            },
        }
        headers = {
            'Content-Type': 'application/json'
        }
        url = '/sign/refuse/%(item_id)s/%(token)s?refusal_reason="test"' % {
             'item_id': sign_request.id,
             'token': sign_request_item.access_token
         }

        # Set the environment user as the public user
        self.uid = self.public_user

        # Send a request to cancel the sign request item
        self.authenticate(None, None)
        response = self.url_open(url, data=dumps(data), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sign_request.state, 'canceled', "Sign request state should be 'canceled'")
        self.assertEqual(sign_request_item.state, 'canceled', "Sign request item state should be 'canceled'")

        sign_cancel_log = self.env['sign.log'].sudo().search([
            ('sign_request_id', '=', sign_request.id),
            ('action', '=', 'cancel')
        ])

        self.assertTrue(sign_cancel_log, "A sign cancel log should be created")
        self.assertEqual(sign_cancel_log.request_state, 'canceled',
                         "Log request state should be 'canceled'")
        self.assertEqual(sign_cancel_log.partner_id, self.partner_1,
                         "Log partner_id should match partner_1")
        self.assertEqual(sign_cancel_log.sign_request_item_id.id, sign_request_item.id,
                         "Log should reference the correct request item")

    def test_make_public_user_with_duplicate_contact(self):
        """
        Test make_public_user behavior with duplicate contacts.
        Ensures that when a user has a duplicate contact with the same email and name,
        the sign request associates the correct partner ID which contains user_ids.
        """
        user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user@example.com',
            'email': 'test_user@example.com',
        })
        contact = user.partner_id

        # Duplicate contact and set the user's partner ID to the duplicate contact
        duplicate_contact = contact.copy()
        user.partner_id = duplicate_contact
        self.assertEqual(user.partner_id, duplicate_contact)
        self.assertEqual(contact.email, duplicate_contact.email)

        # Create a sign request and linked to the user's(Test User) contact
        sign_request = self.env['sign.request'].with_context(no_sign_mail=False).create({
            'template_id': self.template_no_item.id,
            'reference': self.template_no_item.display_name,
            'state': 'shared',
            'request_item_ids': [Command.create({
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
        })

        response = self._json_url_open(
            '/sign/send_public/%s/%s' % (sign_request.id, sign_request.access_token),
            data={'name': contact.name, 'mail': contact.email}
        ).json().get('result')

        self.assertTrue(response.get('requestID'), 'Request ID should be returned')

        sign_request_partner_id = self.env['sign.request'].search(
            [('id', '=', response.get('requestID'))]
        ).request_item_ids.partner_id

        self.assertEqual(
            duplicate_contact.id, sign_request_partner_id.id,
            'The sign request partner ID should match the duplicate contact'
        )
        self.assertEqual(
            sign_request_partner_id.email, contact.email,
            'The email of the sign request partner should match the original contact email'
        )
        self.assertEqual(
            sign_request_partner_id.name, duplicate_contact.name,
            'The name of the sign request partner should match the original contact name'
        )
        self.assertEqual(
            len(sign_request.request_item_ids), 1,
            'There should be exactly one request item in the sign request'
        )

    def test_get_sign_request_items_with_public_user(self):
        """ Test the RPC call to get sign request items as a public user. """
        # Create two sign requests. The second one will be returned as 'the next' to be signed.
        self.sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        self.next_sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        self.sign_request_item = self.sign_request.request_item_ids[0]

        self.authenticate(None, None)  # Ensure the current user for the request is public
        response = self._json_url_open(
            '/sign/sign_request_items',
            {
                'request_id': self.sign_request.id,
                'token': self.sign_request_item.access_token,
                'sign_item_id': self.sign_request_item.id,
            }
        )
        self.assertEqual(response.status_code, 200, f"Expected 200 OK, got {response.status_code}")
        response_json = response.json()  # Get the JSON content of the response
        self.assertEqual(response_json['jsonrpc'], '2.0', "Expected JSON-RPC 2.0 response")
        self.assertNotIn('error', response_json, f"RPC call returned an error: {response_json.get('error')}")

        result = response_json['result']
        self.assertIsInstance(result, list, "Result should be a list")
        self.assertGreaterEqual(len(result), 1, "Should find at least one sign request item")

        # Verify that the found item is the one associated with the test partner's email
        found_item_ids = [item['id'] for item in result]
        self.assertIn(
            self.next_sign_request.request_item_ids[0].id, found_item_ids,
            "The 'next' sign request item must be able to be accessed through the public route."
        )

    def test_get_sign_request_respect_to_order(self):
        """ Test that the thank you dialog only shows documents where it's the user's turn to sign. """
        ordered_request = self.env['sign.request'].create({
            'template_id': self.template_2_roles.id,
            'reference': self.template_2_roles.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_2.id,
                'role_id': self.role_signer_1.id,
                'mail_sent_order': 1,
            }), Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.role_signer_2.id,
                'mail_sent_order': 2,
            })],
        })

        sign_request_1 = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        sign_request_2 = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        ordered_request_item = ordered_request.request_item_ids[1]
        sign_request_item_1 = sign_request_1.request_item_ids[0]
        sign_request_item_2 = sign_request_2.request_item_ids[0]

        self.authenticate(None, None)
        response = self._json_url_open(
            '/sign/sign_request_items',
            {
                'request_id': sign_request_2.id,
                'token': sign_request_item_2.access_token,
                'sign_item_id': sign_request_item_2.id
            }
        )
        response_json = response.json()
        result = response_json['result']
        result_ids = [item['id'] for item in result]
        self.assertIn(sign_request_item_1.id, result_ids,
            "Document where it's the user's turn should appear in the thankyou dialog"
        )
        self.assertNotIn(ordered_request_item.id, result_ids,
            "Document where it's not the user's turn should not appear in the thankyou dialog"
        )

    def test_sign_request_local(self):
        # Make sure the stored signature of an user can't be used by another user locally
        # make sure the log user_id is correct
        # user_1 is linked to partner1
        self.user_1.sign_signature = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC'
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        sign_request_item = sign_request.request_item_ids[0]
        res = sign_request_item.with_user(self.user_2)._get_user_signature(signature_type='sign_signature')
        self.assertFalse(res, "The signature of user1 is not available to user 2")
        res = sign_request_item.with_user(self.user_1)._get_user_signature(signature_type='sign_signature')
        self.assertTrue(res, "The signature of user1 is available to user1")

        sign_vals = self.create_sign_values(sign_request.template_id.sign_item_ids, sign_request_item.role_id.id)
        self.authenticate(self.user_2.login, "user_2!user_2")
        response = self._json_url_open(
            '/sign/sign/%d/%s' % (sign_request.id, sign_request_item.access_token),
            data={'signature': sign_vals}
        ).json()['result']
        self.assertTrue(response['success'], "success request")
        logs = sign_request.sign_log_ids
        create_log = logs.filtered(lambda l: l.action == 'create')
        signature_log = logs.filtered(lambda l: l.action == 'sign')
        self.assertEqual(create_log.create_uid, self.env.user, "the signature is created by current user")
        self.assertEqual(create_log.user_id, self.env.user, "The sign request is created by current user")
        self.assertEqual(signature_log.create_uid, self.user_1, "the signature is created by the signing user")
        self.assertEqual(signature_log.user_id, self.user_2, "the signature log user_id is the logged in user")

    def test_delegate_signer_controller(self):
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        request_item = sign_request.request_item_ids[0]
        # Make the role change_authorized to True to allow delegation
        request_item.role_id.change_authorized = True

        delegate_name = "Delegate User"
        delegate_email = "delegate.user@example.com"

        self.authenticate(None, None)
        with self.mock_mail_gateway():
            result = self._json_url_open(
                    '/sign/delegate_signing/',
                    data={
                        'sign_request_id': sign_request.id,
                        'request_item_id': request_item.id,
                        'request_item_token': request_item.access_token,
                        'delegate_name': delegate_name,
                        'delegate_email': delegate_email,
                    }
                ).json()['result']
            self.assertTrue(result, "Delegation should be successful")
            self.assertEqual(request_item.partner_id.email, delegate_email, "The request item's partner should be updated to the delegate's email")
            self.assertEqual(request_item.partner_id.name, delegate_name, "The request item's partner should be updated to the delegate's name")

            self.assertEqual(len(self._new_mails), 1, "One email should be sent to the delegate")
            self.assertSentEmail('"OdooBot" <odoobot@example.com>', request_item.partner_id)

    def test_download_partially_signed_document(self):
        sign_request = self.create_sign_request_2_roles(
            signer_1=self.partner_1, signer_2=self.partner_2, cc_partners=self.partner_4)
        signer_1 = sign_request.request_item_ids.filtered(lambda item: item.role_id == self.role_signer_1)
        signer_1.sign(self.signer_1_sign_values_2_roles)
        document = sign_request.template_id.document_ids
        url = '/sign/download/%s/%s/%%s/%s' % (sign_request.id, sign_request.access_token, document.id)

        self.authenticate("user_1", "user_1")
        partial = self.url_open(url % 'partial').content
        origin = self.url_open(url % 'origin').content
        sign_request.invalidate_recordset()
        self.assertEqual(origin, bytes(document.attachment_id.raw))
        self.assertTrue(partial.startswith(origin) and partial != origin)
        self.assertEqual(sign_request.request_document_ids.applied_item_ids, signer_1)

        # a user without the sign group has no business downloading the values of the signers
        self.authenticate("user_5", "user_5")
        self.assertEqual(self.url_open(url % 'partial').status_code, 404)

    def test_sign_completed_redirection(self):
        """ Test that internal users are redirected to the backend when a sign request is completed. """
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        sign_request_item = sign_request.request_item_ids[0]
        sign_vals = self.create_sign_values(sign_request.template_id.sign_item_ids, sign_request_item.role_id.id)
        sign_request_item._sign(sign_vals)
        url = '/sign/document/%s/%s' % (sign_request.id, sign_request_item.access_token)

        # Test redirection for a logged-in user with a sign.group_sign_user
        self.authenticate("user_1", "user_1")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(f'/odoo/sign.request/{sign_request.id}/action-sign.Document' in response.url)

        # Test no redirection for a public user
        self.authenticate(None, None)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse('/odoo/sign.request/' in response.url)

        # Test no redirection for an internal user without sign.group_sign_user
        self.authenticate("user_5", "user_5")
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse('/odoo/sign.request/' in response.url)
