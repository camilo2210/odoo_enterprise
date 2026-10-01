import json

from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

from odoo.addons.whatsapp.tests.common import MockIncomingWhatsApp, PROXY_ENDPOINT, WhatsAppCommon
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged('wa_account')
class WhatsAppOAuthAccount(WhatsAppCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._prepare_oauth_account()

    def test_button_disconnect(self):
        """ Disconnecting drops the webhook on both Meta and the proxy. """
        account = self.whatsapp_account_oauth
        with self.mockWhatsappOAuthGateway():
            account.button_disconnect()

        self.assertFalse(account.active)
        self.assertFalse(account.is_webhook_subscribed)
        self.assertFalse(account.proxy_webhook_url)
        self.assertFalse(account.shared_webhook_secret)
        self.assertFalse(account.token)

    def test_button_test_connection(self):
        """ The base test only validates the credentials, so an account that
        cannot send anything must not be reported as successful. """
        account = self.whatsapp_account_oauth

        with self.mockWhatsappOAuthGateway():
            result = account.button_test_connection()
        self.assertEqual(result['params']['type'], 'success')

        with self.mockWhatsappOAuthGateway(is_phone_registered=False, is_webhook_subscribed=False):
            result = account.button_test_connection()
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn("The phone number is not registered", result['params']['message'])

        with self.mockWhatsappOAuthGateway(is_phone_registered=False, is_webhook_subscribed=False):
            result = self.whatsapp_account.button_test_connection()
        self.assertEqual(result['params']['type'], 'success',
                         "A manual account skips the OAuth checks, whatever the onboarding flags say")

    def test_check_account_configured(self):
        """ The onboarding runs before the account exists, and its first calls
        go to the proxy without a token. """
        api = WhatsAppApi(self.env['whatsapp.account'])
        self.assertFalse(api.token)
        api._check_account_configured()

    def test_compute_state(self):
        """ An account is connected only when the phone is registered and the
        webhook still points to the proxy. """
        account = self.whatsapp_account_oauth
        for is_phone_registered, is_webhook_subscribed, expected_state in [
            (True, True, 'connected'),
            (True, False, 'disconnected'),
            (False, True, 'disconnected'),
            (False, False, 'disconnected'),
        ]:
            with self.subTest(is_phone_registered=is_phone_registered, is_webhook_subscribed=is_webhook_subscribed):
                account.write({
                    'is_phone_registered': is_phone_registered,
                    'is_webhook_subscribed': is_webhook_subscribed,
                })
                self.assertEqual(account.state, expected_state)

        self.assertFalse(self.whatsapp_account.state, "A manually configured account has no state")

    @mute_logger('odoo.addons.whatsapp.models.whatsapp_account')
    def test_cron_refresh_onboarded_account_state(self):
        """ The cron refreshes onboarded accounts and survives an API error. """
        account = self.whatsapp_account_oauth

        with self.mockWhatsappOAuthGateway(is_phone_registered=False, is_webhook_subscribed=False):
            self.env['whatsapp.account']._cron_refresh_onboarded_account_state()
        self.assertFalse(account.is_phone_registered)
        self.assertFalse(account.is_webhook_subscribed)

        with self.mockWhatsappOAuthGateway():
            self.env['whatsapp.account']._cron_refresh_onboarded_account_state()
        self.assertTrue(account.is_phone_registered)
        self.assertTrue(account.is_webhook_subscribed)

        # An account that cannot be reached is left untouched and does not stop the cron.
        with patch.object(WhatsAppApi, '_fetch_account_state', side_effect=WhatsAppError('Token expired', 190)):
            self.env['whatsapp.account']._cron_refresh_onboarded_account_state()
        self.assertTrue(account.is_phone_registered)
        self.assertTrue(account.is_webhook_subscribed)
        self.assertEqual(account.state, 'connected')

    def test_fetch_onboarded_phone_number_data(self):
        """ The number just onboarded is taken, and an account without one is refused. """
        waba_id = 'waba_onboarded_789'
        api = WhatsAppApi(self.env['whatsapp.account'], token='onboarding_token')
        # Meta sorts by last onboarded time, so the number just onboarded comes first.
        with self.mockWhatsappOAuthGateway(phone_numbers=[
            {'id': 'latest_phone'},
            {'id': 'older_phone'},
        ]):
            self.assertEqual(api._fetch_onboarded_phone_number_data(waba_id)['id'], 'latest_phone')

        with (
            self.mockWhatsappOAuthGateway(phone_numbers=[]),
            self.assertRaises(WhatsAppError) as capture,
        ):
            api._fetch_onboarded_phone_number_data(waba_id)
        self.assertIn("does not have any Cloud API phone numbers", capture.exception.error_message)

    def test_fetch_onboarded_waba_id(self):
        """ The account just shared is taken, and nothing else counts as onboarded. """
        api = WhatsAppApi(self.env['whatsapp.account'], token='onboarding_token')
        # Meta returns the accounts in onboarding order, most recent first.
        with self.mockWhatsappOAuthGateway(granular_scopes=[
            {'scope': 'whatsapp_business_management', 'target_ids': ['latest_waba', 'older_waba']},
        ]):
            self.assertEqual(api._fetch_onboarded_waba_id(), 'latest_waba')

        for case, granular_scopes in [
            ("nothing shared", []),
            ("only the messaging scope", [{'scope': 'whatsapp_business_messaging', 'target_ids': ['ignored_id']}]),
            ("the right scope, no account", [{'scope': 'whatsapp_business_management', 'target_ids': []}]),
        ]:
            with self.subTest(case=case):
                with (
                    self.mockWhatsappOAuthGateway(granular_scopes=granular_scopes),
                    self.assertRaises(WhatsAppError) as capture,
                ):
                    api._fetch_onboarded_waba_id()
                self.assertIn("No WhatsApp Business Account was found", capture.exception.error_message)

    def test_refresh_account_state(self):
        """ Both flags are read again on Meta, as nothing warns us when the
        phone is deregistered or when another provider takes the webhook. """
        account = self.whatsapp_account_oauth
        with self.mockWhatsappOAuthGateway():
            account._refresh_account_state()
        self.assertTrue(account.is_phone_registered)
        self.assertTrue(account.is_webhook_subscribed)
        self.assertEqual(account.state, 'connected')

        with self.mockWhatsappOAuthGateway(is_phone_registered=False, is_webhook_subscribed=False):
            account._refresh_account_state()
        self.assertFalse(account.is_phone_registered)
        self.assertFalse(account.is_webhook_subscribed, "The webhook was taken over by another provider")
        self.assertEqual(account.state, 'disconnected')

    def test_register_phone(self):
        """ Registering needs the number's two-step verification PIN, a wrong one changes nothing. """
        account = self.whatsapp_account_oauth
        account.is_phone_registered = False
        wizard = self.env['whatsapp.register.phone'].with_user(self.user_wa_admin).create({
            'pin': '123456',
            'wa_account_id': account.id,
        })

        with (
            self.mockWhatsappOAuthGateway(register_phone_error='Two-step verification PIN incorrect.'),
            self.assertRaises(UserError) as capture,
        ):
            wizard.action_register_phone()
        self.assertIn('Two-step verification PIN incorrect.', str(capture.exception))
        self.assertFalse(account.is_phone_registered)

        with self.mockWhatsappOAuthGateway():
            wizard.action_register_phone()
        self.assertTrue(account.is_phone_registered)


@tagged('wa_account', 'post_install', '-at_install')
class WhatsAppOAuthController(MockIncomingWhatsApp, WhatsAppCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._prepare_oauth_account()

    def test_check_signature_manual_account(self):
        """ Accounts configured by hand keep using the app secret. """
        account = self.whatsapp_account
        payload = json.dumps({'entry': [{'id': account.account_uid}]})

        response = self._make_webhook_request(
            account, message_data=payload,
            headers={'X-Hub-Signature-256': f'sha256={self._get_message_signature(account, payload)}'},
        )
        self.assertNotIn('error', response, "A valid Meta signature is still accepted")

    @mute_logger('odoo.addons.whatsapp.controller.main')
    def test_check_signature_oauth_account(self):
        """ Onboarded accounts are signed by the proxy, not by Meta. """
        account = self.whatsapp_account_oauth
        payload = json.dumps({'entry': [{'id': account.account_uid}]})
        signature = self._get_proxy_signature(account, payload)

        # The proxy signs the forwarded event with the shared secret.
        response = self._make_webhook_request(
            account, message_data=payload,
            headers={'IAP-Signature-256': f'sha256={signature}'},
        )
        self.assertNotIn('error', response, "A valid proxy signature is accepted")

        # Every other shape is rejected, Meta's own header included.
        for header, value in [
            ('IAP-Signature-256', False),  # no signature
            ('IAP-Signature-256', 'sha256='),  # empty
            ('IAP-Signature-256', signature),  # wrong format
            ('IAP-Signature-256', f'sha256={self._get_proxy_signature(account, payload + "x")}'),  # wrong payload
            ('X-Hub-Signature-256', f'sha256={signature}'),  # meta header, right secret
        ]:
            with self.subTest(header=header, value=value):
                response = self._make_webhook_request(
                    account, message_data=payload,
                    headers={header: value} if value else None,
                )
                self.assertIn("403 Forbidden", response.get('error', {}).get('data', {}).get('message'))

        # Without the secret there is nothing to verify a correct signature against.
        account.shared_webhook_secret = False
        response = self._make_webhook_request(
            account, message_data=payload,
            headers={'IAP-Signature-256': f'sha256={signature}'},
        )
        self.assertIn("403 Forbidden", response.get('error', {}).get('data', {}).get('message'))

    @mute_logger('odoo.addons.whatsapp.controller.onboarding')
    def test_onboarding_errors(self):
        """ Every failure lands on the error page instead of a traceback. """
        self.authenticate('user_wa_admin', 'user_wa_admin')
        action = self.make_jsonrpc_request('/whatsapp/start_onboarding')
        csrf_token = parse_qs(urlsplit(action['url']).query)['csrf_token'][0]

        # A forged CSRF token never reaches the flow.
        response = self.url_open('/whatsapp/oauth/return?' + urlencode({
            'csrf_token': 'wrong_token',
            'error': 'subscription_error',
        }))
        self.assertEqual(response.status_code, 403)

        # The proxy rejected the database before the Meta dialog.
        response = self.url_open('/whatsapp/oauth/return?' + urlencode({
            'csrf_token': csrf_token,
            'error': 'subscription_error',
        }))
        self.assertIn("The Enterprise subscription could not be validated.", response.text)

        # The proxy came back without an authorization code.
        response = self.url_open('/whatsapp/oauth/return?' + urlencode({'csrf_token': csrf_token}))
        self.assertIn("The WhatsApp proxy did not return the required information.", response.text)

        # The code was exchanged but no token came back.
        with self.mockWhatsappOAuthGateway(access_token=False):
            response = self.url_open('/whatsapp/oauth/return?' + urlencode({
                'authorization_code': 'authorization_code',
                'csrf_token': csrf_token,
                'whatsapp_app_id': 'app_new_456',
            }))
        self.assertIn("The WhatsApp proxy did not return an access token.", response.text)

    def test_onboarding_flow(self):
        """ The returning call creates the account, then updates it on a second run. """
        self.authenticate('user_wa_admin', 'user_wa_admin')
        action = self.make_jsonrpc_request('/whatsapp/start_onboarding')
        csrf_token = parse_qs(urlsplit(action['url']).query)['csrf_token'][0]

        waba_id, phone_uid = 'waba_new_456', '999888777'
        phone_number_data = {
            'display_phone_number': '+1 555-0199',
            'id': phone_uid,
            'status': 'CONNECTED',
            'verified_name': 'New Business',
        }
        return_url = '/whatsapp/oauth/return?' + urlencode({
            'authorization_code': 'authorization_code',
            'csrf_token': csrf_token,
            'whatsapp_app_id': 'app_new_456',
        })

        with self.mockWhatsappOAuthGateway(
            phone_numbers=[phone_number_data],
            granular_scopes=[
                {'scope': 'whatsapp_business_messaging', 'target_ids': ['ignored_id']},
                {'scope': 'whatsapp_business_management', 'target_ids': [waba_id]},
            ],
        ):
            response = self.url_open(return_url, allow_redirects=False)
        self.assertEqual(response.status_code, 303)

        account = self.env['whatsapp.account'].search([('phone_uid', '=', phone_uid)])
        self.assertEqual(len(account), 1)
        self.assertEqual(account.account_uid, waba_id)
        self.assertEqual(account.app_uid, 'app_new_456')
        self.assertEqual(account.name, 'New Business')
        self.assertEqual(account.phone_number, '+1 555-0199')
        self.assertEqual(account.state, 'connected')
        self.assertTrue(account.is_oauth_onboarded)
        self.assertEqual(account.sudo().token, 'new_access_token')
        self.assertEqual(account.sudo().shared_webhook_secret, 'new_shared_secret')
        self.assertEqual(account.sudo().proxy_webhook_url, f'{PROXY_ENDPOINT}/webhook/new_hook')

        phone_number_data['verified_name'] = 'Renamed Business'
        with self.mockWhatsappOAuthGateway(
            phone_numbers=[phone_number_data],
            granular_scopes=[
                {'scope': 'whatsapp_business_messaging', 'target_ids': ['ignored_id']},
                {'scope': 'whatsapp_business_management', 'target_ids': [waba_id]},
            ],
        ):
            response = self.url_open(return_url, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            self.env['whatsapp.account'].with_context(active_test=False).search_count([('phone_uid', '=', phone_uid)]),
            1, "Onboarding the same number again updates the account instead of creating a second one",
        )
        self.assertEqual(account.name, 'Renamed Business')

    def test_start_onboarding(self):
        """ A WhatsApp administrator is not necessarily a settings administrator. """
        self.authenticate('user_wa_admin', 'user_wa_admin')
        action = self.make_jsonrpc_request('/whatsapp/start_onboarding')

        self.assertEqual(action['type'], 'ir.actions.act_url')
        params = parse_qs(urlsplit(action['url']).query)
        self.assertTrue(action['url'].startswith(f'{PROXY_ENDPOINT}/authorize?'))
        self.assertEqual(
            params['db_uuid'],
            [self.env['ir.config_parameter'].sudo().get_str('database.uuid')],
        )
        self.assertTrue(params['return_url'][0].endswith('/whatsapp/oauth/return'))
