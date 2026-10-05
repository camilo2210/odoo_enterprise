import json

from odoo.tests import tagged

from odoo.addons.ai_mcp.tests.oauth_common import REDIRECT_URI, OauthServerCommon
from odoo.addons.ai_mcp.utils.oauth_utils import oauth_base_url


@tagged('post_install', '-at_install')
class TestBearerProtectedRoute(OauthServerCommon):

    def test_missing_bearer_token_is_rejected_with_resource_metadata_hint(self):
        response = self.url_open('/mcp', data='{}')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.headers.get('WWW-Authenticate'),
            f'Bearer resource_metadata="{oauth_base_url(self.env)}/.well-known/oauth-protected-resource/mcp"',
        )

    def test_access_token_of_inactive_user_is_rejected_on_a_bearer_protected_route(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        access_token = self._generate_access_token(
            code, client_id=client_id,
        ).json()['access_token']
        self.authenticate(None, None)
        mcp_ping = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        bearer_headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        self.assertEqual(self.url_open('/mcp', data=mcp_ping, headers=bearer_headers).status_code, 200)

        self.internal_user.active = False
        self.assertEqual(self.url_open('/mcp', data=mcp_ping, headers=bearer_headers).status_code, 401)
