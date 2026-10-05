import re
from urllib.parse import parse_qs, urlsplit, unquote

from odoo.tests import tagged

from .oauth_common import REDIRECT_URI, OauthServerCommon
from odoo.addons.ai_mcp.utils.oauth_utils import oauth_base_url


@tagged('post_install', '-at_install')
class TestAuthCodeGeneration(OauthServerCommon):

    def test_not_logged_in_user_is_redirected_to_login(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        response = self._authorize(client_id=client_id, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('/web/login', response.headers['Location'])

    def test_consent_screen_is_shown_and_not_frameable(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        response = self._authorize(client_id=client_id)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "<strong>Test Client</strong> is requesting access to your Odoo account for <strong>MCP (Model Context Protocol)</strong>",
            re.sub(r"\s+", " ", response.text)
        )
        self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')
        self.assertIn("frame-ancestors 'none'", response.headers.get('Content-Security-Policy', ''))

    def test_consent_screen_ignores_a_client_name_sent_by_the_client(self):
        """A client must not be able to present itself under a name it did not register."""
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        response = self._authorize(client_id=client_id, client_name='Microsoft Copilot (Verified)')
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "<strong>Test Client</strong> is requesting access to your Odoo account for <strong>MCP (Model Context Protocol)</strong>",
            re.sub(r"\s+", " ", response.text)
        )
        self.assertNotIn('Microsoft Copilot', response.text)

    def test_consent_screen_offers_the_durations_allowed_for_the_user(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('regular_user', 'regular_user')
        # base.group_user_regular caps API keys at 90 days, so a year is not offered.
        response = self._authorize(client_id=client_id)
        self.assertIn('id="oauth_duration_1" value="1"', response.text)
        self.assertIn('id="oauth_duration_30" value="30" checked', response.text)
        self.assertNotIn('value="365"', response.text)
        self.assertNotIn('value="0"', response.text)

        self.env.ref('base.group_user_regular').api_key_duration = 1
        response = self._authorize(client_id=client_id)
        self.assertIn('id="oauth_duration_1" value="1" checked', response.text)
        self.assertNotIn('value="30"', response.text)
        self.assertNotIn('value="365"', response.text)
        self.assertNotIn('value="0"', response.text)

        self.authenticate('admin', 'admin')
        response = self._authorize(client_id=client_id)
        self.assertIn('id="oauth_duration_1" value="1"', response.text)
        self.assertIn('id="oauth_duration_30" value="30" checked', response.text)
        self.assertIn('value="365"', response.text)
        self.assertIn('value="0"', response.text)

    def test_consent_approval_issues_code_with_iss(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')

        response = self._submit_consent(client_id=client_id)
        self.assertEqual(response.status_code, 303)
        location = unquote(response.headers['Location'])
        self.assertTrue(location.startswith(REDIRECT_URI))
        self.assertIn('code=', location)
        self.assertIn(f'iss={oauth_base_url(self.env)}/oauth/mcp', location)

    def test_consent_screen_does_not_echo_the_decision_parameters(self):
        """A malicious client must not be able to pre-fill the controls of the consent screen.

        The attack this test asserts is not possible:
        1. The attacker sends the user an authorization request that already carries the
           parameters of the consent screen: /oauth/authorize?...&allow=true&duration=0
        2. The consent screen echoes them back as hidden inputs, which sit in the form before
           the Allow/Deny buttons, so submitting it sends allow=true and then the clicked value.
        3. Werkzeug keeps the first value of a duplicated field, so allow=true wins: clicking
           Deny hands the attacker an authorization code anyway.
           The same can be done with passing duration=0 which makes the API
           key behind that code never expire.
        """
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        response = self._authorize(
            client_id=client_id,
            allow='true',
            duration='0',
            csrf_token='forged',
        )
        self.assertEqual(response.status_code, 200)

        hidden_inputs = dict(re.findall(r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"', response.text))
        self.assertNotIn('allow', hidden_inputs)
        self.assertNotIn('duration', hidden_inputs)
        self.assertNotEqual(hidden_inputs['csrf_token'], 'forged')

    def test_consent_denial_redirects_with_access_denied(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        response = self._submit_consent(client_id=client_id, allow='false')
        self.assertIn('error=access_denied', response.headers['Location'])

    def test_arbitrary_requested_scope_is_ignored(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        response = self._submit_consent(client_id=client_id, scope='read delete_everything')
        self.assertEqual(response.status_code, 303)

        auth_code = self.env['oauth.authorization.code']._retrieve_record(
            code=parse_qs(urlsplit(response.headers['Location']).query)['code'][0],
            client_id=client_id,
            redirect_uri=REDIRECT_URI,
        )
        self.assertTrue(auth_code)

    def test_non_internal_user_is_not_shown_the_consent_screen(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('portal_user', 'portal_user')
        response = self._authorize(client_id=client_id)
        self.assertEqual(response.status_code, 400, response.text)

        response_json = response.json()
        self.assertEqual(response_json['error'], 'authorization_failed')
        self.assertEqual(response_json['error_description'], "Only internal users are allowed to use oauth for mcp")

    def test_user_access_is_rechecked_when_the_consent_is_submitted(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        # internal_user is allowed, so authorize renders the consent screen.
        response = self._authorize(client_id=client_id)
        self.assertIn(
            "<strong>Test Client</strong> is requesting access to your Odoo account for <strong>MCP (Model Context Protocol)</strong>",
            re.sub(r"\s+", " ", response.text)
        )

        self.authenticate('portal_user', 'portal_user')
        response = self._submit_consent(client_id=client_id)
        self.assertEqual(response.status_code, 400, response.text)
        response_json = response.json()
        self.assertEqual(response_json['error'], 'authorization_failed')
        self.assertEqual(response_json['error_description'], "Only internal users are allowed to use oauth for mcp")

        client = self.env['oauth.client'].search([('client_id', '=', client_id)])
        self.assertFalse(self.env['oauth.authorization.code'].search([('client_id', '=', client.client_id)]))

    def test_loopback_redirect_uri_matches_regardless_of_port(self):
        self.authenticate('internal_user', 'internal_user')
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': 'http://127.0.0.1:8080/cb'
        }).client_id
        response = self._authorize(client_id=client_id, redirect_uri='http://127.0.0.1:54321/cb')
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'name="redirect_uri" value="http://127.0.0.1:54321/cb"',
            response.text
        )

    def test_localhost_redirect_uri_is_normalized_to_ip(self):
        """"localhost" resolution can be hijacked (DNS rebinding, hosts file) as per RFC 8252 §8.3.
        So it is substituted with 127.0.0.1.
        """
        self.authenticate('internal_user', 'internal_user')
        client = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': 'http://localhost:8080/cb'
        })

        response = self._authorize(client_id=client.client_id, redirect_uri='http://localhost:54321/cb')
        self.assertEqual(response.status_code, 200)
        # redirect_uri param of the authorize request is normalized to use 127.0.0.1 instead of localhost
        self.assertIn(
            'name="redirect_uri" value="http://127.0.0.1:54321/cb"',
            response.text
        )

        consent_response = self._submit_consent(client_id=client.client_id, redirect_uri='http://localhost:54321/cb')
        self.assertEqual(consent_response.status_code, 303)
        self.assertTrue(consent_response.headers['Location'].startswith('http://127.0.0.1:54321/cb?'))

        authorization_code = self.env['oauth.authorization.code'].search([('client_id', '=', client.client_id)])
        self.assertEqual(authorization_code.redirect_uri, 'http://127.0.0.1:54321/cb')

    def test_loopback_redirect_uri_path_mismatch_rejection(self):
        self.authenticate('internal_user', 'internal_user')
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': 'http://127.0.0.1:8080/cb'
        }).client_id
        response = self._authorize(client_id=client_id, redirect_uri='http://127.0.0.1:54321/other')
        self.assertEqual(response.status_code, 400)

        response_json = response.json()
        self.assertEqual(response_json['error'], 'authorization_failed')
        self.assertEqual(response_json['error_description'], "redirect_uri is not registered for this client")

    def test_loopback_redirect_uri_query_mismatch_rejection(self):
        self.authenticate('internal_user', 'internal_user')
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': 'http://127.0.0.1:8080/cb'
        }).client_id
        response = self._authorize(client_id=client_id, redirect_uri='http://127.0.0.1:8080/cb?injected=1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error_description'], "redirect_uri is not registered for this client")

    def test_redirect_uri_with_fragment_is_rejected(self):
        self.authenticate('internal_user', 'internal_user')
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': 'http://127.0.0.1:8080/cb'
        }).client_id
        response = self._authorize(client_id=client_id, redirect_uri='http://127.0.0.1:8080/cb#fragment')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error_description'], "redirect_uri is not registered for this client")

    def test_auth_code_is_appended_to_query_params(self):
        """A redirect_uri may already carry query params, which must stay intact"""
        self.authenticate('internal_user', 'internal_user')
        redirect_uri = 'https://client.example.com/cb?tenant=acme'
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': redirect_uri
        }).client_id

        for allow, expected_param in [('true', 'code='), ('false', 'error=access_denied')]:
            with self.subTest(allow=allow):
                response = self._submit_consent(client_id=client_id, redirect_uri=redirect_uri, allow=allow)
                location = response.headers['Location']
                self.assertEqual(location.count('?'), 1)
                self.assertIn('tenant=acme', location)
                self.assertIn(expected_param, location)

    def test_unregistered_redirect_uri_is_rejected(self):
        self.authenticate('internal_user', 'internal_user')
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        response = self._authorize(client_id=client_id, redirect_uri='https://evil.example.com/callback')
        self.assertEqual(response.status_code, 400)

        response_json = response.json()
        self.assertEqual(response_json['error'], 'authorization_failed')
        self.assertEqual(response_json['error_description'], "redirect_uri is not registered for this client")

    def test_inactive_client_cannot_generate_an_auth_code(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        client = self.env['oauth.client'].search([('client_id', '=', client_id)])
        client.action_archive()
        self.authenticate('internal_user', 'internal_user')

        authorize_response = self._authorize(client_id=client_id)
        self.assertEqual(authorize_response.status_code, 401, authorize_response.text)
        self.assertEqual(authorize_response.json()['error'], 'invalid_client')
        self.assertEqual(authorize_response.json()['error_description'], "Invalid client credentials")

        # An archived client can't generate a code from a consent screen rendered before it was archived.
        consent_response = self._submit_consent(client_id=client_id)
        self.assertEqual(consent_response.status_code, 401, consent_response.text)
        self.assertEqual(consent_response.json()['error'], "invalid_client")
        self.assertEqual(authorize_response.json()['error_description'], "Invalid client credentials")
        self.assertFalse(self.env['oauth.authorization.code'].search([('client_id', '=', client.client_id)]))
