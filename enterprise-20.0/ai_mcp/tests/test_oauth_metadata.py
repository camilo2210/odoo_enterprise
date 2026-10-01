from unittest.mock import patch

from odoo.tests import HttpCase, tagged

OAUTH_BASE_URL = 'https://oauth.example.com'


@tagged('post_install', '-at_install')
class TestOauthServerMetadata(HttpCase):

    def test_protected_resource_metadata(self):
        with patch(
            'odoo.addons.ai_mcp.controllers.oauth_server_controller.oauth_base_url',
            return_value=OAUTH_BASE_URL
        ):
            response = self.url_open('/.well-known/oauth-protected-resource/mcp')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                'resource': f'{OAUTH_BASE_URL}/mcp',
                'authorization_servers': [f'{OAUTH_BASE_URL}/oauth/mcp'],
            })

    def test_authorization_server_metadata(self):
        with patch(
            'odoo.addons.ai_mcp.controllers.oauth_server_controller.oauth_base_url',
            return_value=OAUTH_BASE_URL
        ):
            response = self.url_open('/.well-known/oauth-authorization-server/oauth/mcp')
            self.assertEqual(response.status_code, 200)

            expected_metadata = {
                'issuer': f'{OAUTH_BASE_URL}/oauth/mcp',
                'authorization_endpoint': f'{OAUTH_BASE_URL}/oauth/authorize',
                'token_endpoint': f'{OAUTH_BASE_URL}/oauth/token',
                'revocation_endpoint': f'{OAUTH_BASE_URL}/oauth/revoke',
                'response_types_supported': ['code'],
                'grant_types_supported': ['authorization_code'],
                'code_challenge_methods_supported': ['S256'],
                'token_endpoint_auth_methods_supported': ['none'],
                'scopes_supported': ['mcp'],
                'client_id_metadata_document_supported': True,
                'authorization_response_iss_parameter_supported': True,
            }
            self.assertEqual(response.json(), expected_metadata)
