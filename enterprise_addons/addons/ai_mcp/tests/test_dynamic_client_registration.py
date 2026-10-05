import json
from unittest.mock import patch

from odoo.tests import tagged

from .oauth_common import REDIRECT_URI, OauthServerCommon


@tagged('post_install', '-at_install')
class TestDynamicClientRegistration(OauthServerCommon):

    def _register_client_dynamically(self, redirect_uris=(REDIRECT_URI,), auth_method='none'):
        params = {
            'client_name': 'Test Client',
            'redirect_uris': list(redirect_uris),
        }
        if auth_method:
            params['token_endpoint_auth_method'] = auth_method
        response = self.url_open(
            '/oauth/register/mcp',
            data=json.dumps(params),
            headers={'Content-Type': 'application/json'}
        )
        return response.json()

    def _enable_dcr(self):
        self.env['ir.config_parameter'].sudo().set_bool('enable_dcr', True)

    def _disable_dcr(self):
        self.env['ir.config_parameter'].sudo().set_bool('enable_dcr', False)

    def _get_authorization_server_metadata(self):
        with patch(
            'odoo.addons.ai_mcp.controllers.oauth_server_controller.oauth_base_url',
            return_value='https://oauth.example.com'
        ):
            response = self.url_open('/.well-known/oauth-authorization-server/oauth/mcp')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_authorization_server_metadata_advertises_the_registration_endpoint(self):
        self._enable_dcr()
        metadata = self._get_authorization_server_metadata()
        self.assertEqual(
            metadata['registration_endpoint'],
            'https://oauth.example.com/oauth/register/mcp',
        )

    def test_authorization_server_metadata_hides_the_registration_endpoint_when_dcr_is_disabled(self):
        self._disable_dcr()
        metadata = self._get_authorization_server_metadata()

        self.assertNotIn('registration_endpoint', metadata)
        self.assertTrue(metadata['client_id_metadata_document_supported'])

    def test_registration_is_refused_when_dcr_is_disabled(self):
        self._disable_dcr()
        response = self.url_open(
            '/oauth/register/mcp',
            data=json.dumps({'client_name': 'Test Client', 'redirect_uris': [REDIRECT_URI]}),
            headers={'Content-Type': 'application/json'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'access_denied')
        self.assertEqual(response.json()['error_description'], 'Dynamic client registration is disabled on this server.')
        self.assertFalse(self.env['oauth.client'].search([('client_name', '=', 'Test Client')]))

        self._enable_dcr()
        self.assertIn('client_id', self._register_client_dynamically())

    def test_client_registration(self):
        self._enable_dcr()
        # token_endpoint_auth_method defaults to "none" when it is missing.
        response = self._register_client_dynamically(auth_method=None)
        self.assertTrue(response['client_id'])
        self.assertEqual(response['token_endpoint_auth_method'], 'none')

        response = self._register_client_dynamically(auth_method='none')
        self.assertTrue(response['client_id'])
        self.assertEqual(response['token_endpoint_auth_method'], 'none')

        for auth_method in ('client_secret_post', 'client_secret_basic', 'private_key_jwt'):
            response = self._register_client_dynamically(auth_method=auth_method)
            self.assertEqual(response['error'], 'invalid_client_metadata')
            self.assertEqual(
                response['error_description'],
                f'Unsupported token_endpoint_auth_method {auth_method}',
            )

    def test_register_allows_https_or_loopback_only_http_redirect_uri(self):
        self._enable_dcr()
        response = self._register_client_dynamically(redirect_uris=["https://www.example.com:8080/cb"])
        self.assertNotIn('error', response)
        self.assertIn('client_id', response)

        response = self._register_client_dynamically(["http://localhost:8080/cb"])
        self.assertNotIn('error', response)
        self.assertIn('client_id', response)

        response = self._register_client_dynamically(["https://www.example.com:1234/cb", "http://localhost:8080/cb"])
        self.assertNotIn('error', response)
        self.assertIn('client_id', response)

        response = self._register_client_dynamically(redirect_uris=["http://127.0.0.1:8080/cb"])
        self.assertNotIn('error', response)
        self.assertIn('client_id', response)

        response = self._register_client_dynamically(redirect_uris=[])
        self.assertEqual(response['error'], "invalid_client_metadata")

        response = self._register_client_dynamically(redirect_uris=["http://client.example.com/callback"])
        self.assertEqual(response['error'], 'invalid_client_metadata')

    def test_register_rejects_redirect_uri_with_fragment(self):
        self._enable_dcr()
        response = self._register_client_dynamically(redirect_uris=["https://client.example.com/cb#fragment"])
        self.assertEqual(response['error'], 'invalid_client_metadata')
