import json
from contextlib import contextmanager
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from odoo.tests import tagged

from .oauth_common import REDIRECT_URI, OauthServerCommon

CIMD_CLIENT_ID = 'https://client.example.com/oauth/client.json'


@tagged('post_install', '-at_install')
class TestClientIdMetadataDocument(OauthServerCommon):

    def _cimd_document(self, **overrides):
        return {
            'client_id': CIMD_CLIENT_ID,
            'client_name': 'CIMD Test Client',
            'redirect_uris': [REDIRECT_URI],
            'token_endpoint_auth_method': 'none',
            **overrides,
        }

    @contextmanager
    def _mock_cimd_fetch(self, document=None):
        # Only the network call is mocked, the document is still validated by the server.
        response = Mock(status_code=200)
        response.raw.read.return_value = json.dumps(self._cimd_document() if document is None else document).encode()
        with patch('odoo.addons.ai_mcp.utils.oauth_utils.requests.get', return_value=response) as mocked_get:
            yield mocked_get

    def test_authorization_server_metadata_advertises_cimd(self):
        metadata = self.url_open('/.well-known/oauth-authorization-server/oauth/mcp').json()
        self.assertTrue(metadata['client_id_metadata_document_supported'])
        self.assertTrue(metadata['authorization_response_iss_parameter_supported'])

    def test_allowed_cimd_clients(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        with self._mock_cimd_fetch():
            response = self._authorize(client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 200)
        # Everything shown about the client comes from the document, nothing is registered locally.
        self.assertIn('CIMD Test Client', response.text)
        self.assertFalse(self.env['oauth.client'].sudo().search([('client_id', '=', CIMD_CLIENT_ID)]))

        with self._mock_cimd_fetch() as mocked_get:
            response = self._authorize(client_id="https://www.example.com")
        mocked_get.assert_not_called()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_client')
        self.assertIn("CIMD URL https://www.example.com isn't allowed", response.json()['error_description'])

    def test_removing_the_url_from_the_allow_list_revokes_the_client(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        with self._mock_cimd_fetch():
            response = self._authorize(client_id=CIMD_CLIENT_ID)
        self.assertEqual(response.status_code, 200)

        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', '')
        with self._mock_cimd_fetch():
            response = self._authorize(client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 401)
        self.assertIn(f"CIMD URL {CIMD_CLIENT_ID} isn't allowed", response.json()['error_description'])

    def test_document_client_id_must_match_the_url_it_was_fetched_from(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        document = self._cimd_document(client_id='https://client.example.com/oauth/other.json')
        with self._mock_cimd_fetch(document):
            self.authenticate('internal_user', 'internal_user')
            response = self._authorize(client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 401)
        self.assertIn(f'The client_id of the metadata document does not match the URL {CIMD_CLIENT_ID} it was fetched from.', response.json()['error_description'])

    def test_a_client_supporting_none_among_other_auth_methods_is_accepted(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        document = self._cimd_document(
            token_endpoint_auth_method='private_key_jwt',
            token_endpoint_auth_methods_supported=['none', 'private_key_jwt'],
        )
        with self._mock_cimd_fetch(document):
            response = self._authorize(client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 200)
        self.assertIn('CIMD Test Client', response.text)

    def test_a_client_that_does_not_support_none_is_refused(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        document = self._cimd_document(
            token_endpoint_auth_method='private_key_jwt',
            token_endpoint_auth_methods_supported=['private_key_jwt'],
        )
        with self._mock_cimd_fetch(document):
            response = self._authorize(client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 401)
        self.assertIn('Unsupported token_endpoint_auth_method', response.json()['error_description'])

    def test_redirect_uri_must_be_listed_in_the_document(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        with self._mock_cimd_fetch():
            response = self._authorize(client_id=CIMD_CLIENT_ID, redirect_uri='https://client.example.com/other-callback')

        self.assertEqual(response.status_code, 400)
        self.assertIn('redirect_uri is not registered', response.json()['error_description'])

    def test_the_submit_consent_endpoint_refuses_a_client_that_is_not_on_the_allow_list(self):
        self.authenticate('internal_user', 'internal_user')
        with self._mock_cimd_fetch():
            response = self._submit_consent(client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 401)
        self.assertIn(f"CIMD URL {CIMD_CLIENT_ID} isn't allowed", response.json()['error_description'])

    def test_full_cimd_authorization_code_exchange_generates_an_access_token(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        with self._mock_cimd_fetch():
            consent_response = self._submit_consent(client_id=CIMD_CLIENT_ID)
            code = parse_qs(urlsplit(consent_response.headers['Location']).query)['code'][0]
            response = self._generate_access_token(code, client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['access_token'])
        self.assertEqual(response.json()['scope'], 'mcp')

    def test_the_token_endpoint_refuses_a_client_that_is_not_on_the_allow_list(self):
        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', CIMD_CLIENT_ID)
        self.authenticate('internal_user', 'internal_user')
        with self._mock_cimd_fetch():
            code = self._generate_auth_code(client_id=CIMD_CLIENT_ID)

        self.env['ir.config_parameter'].sudo().set_str('cimd_allowed_urls', '')
        response = self._generate_access_token(code, client_id=CIMD_CLIENT_ID)

        self.assertEqual(response.status_code, 401)
        self.assertIn(f"CIMD URL {CIMD_CLIENT_ID} isn't allowed", response.json()['error_description'])
