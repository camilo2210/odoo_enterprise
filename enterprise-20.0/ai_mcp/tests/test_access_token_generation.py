from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import new_test_user, tagged

from .oauth_common import REDIRECT_URI, OauthServerCommon


@tagged('post_install', '-at_install')
class TestAccessTokenGeneration(OauthServerCommon):

    def test_full_authorization_code_exchange_generates_access_token(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')

        code = self._generate_auth_code(client_id=client_id)
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 200, response.text)
        response_json = response.json()
        self.assertEqual(response_json['scope'], 'mcp')
        self.assertEqual(response_json['token_type'], 'Bearer')

        self.assertEqual(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=response_json['access_token']), self.internal_user.id)

    def test_apikey_name_ignores_a_client_name_sent_by_the_client(self):
        """A client must not be able to label its key with a name it did not register."""
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        self._generate_access_token(code, client_id=client_id, client_name='Microsoft Copilot (Verified)')
        self.assertEqual(
            self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')]).mapped('name'),
            ['Test Client'],
        )

    def test_access_token_is_not_valid_for_another_scope(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        access_token = self._generate_access_token(code, client_id=client_id).json()['access_token']

        self.assertIsNone(self.env['res.users.apikeys']._check_credentials(scope='other_scope', key=access_token))

    def test_missing_client_id_is_rejected(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        response = self._generate_access_token(code)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_client')

    def test_token_endpoint_rejects_an_unknown_client_id(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        token_result = {
            'access_token': 'access_token', 'token_type': 'Bearer', 'expires_in': 600, 'scope': 'mcp',
        }
        with patch(
            'odoo.addons.ai_mcp.models.oauth_authorization_code.OauthAuthorizationCode._redeem',
            return_value=token_result,
        ) as redeem_mock:
            response = self._generate_access_token('authorization_code', client_id='unknown-client-id')
            self.assertEqual(response.status_code, 401, response.text)
            self.assertEqual(response.json()['error'], 'invalid_client')
            self.assertEqual(response.json()['error_description'], "Invalid client credentials")
            redeem_mock.assert_not_called()

            response = self._generate_access_token('authorization_code', client_id=client_id)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), token_result)
            redeem_mock.assert_called_once()

    def test_wrong_code_verifier_is_rejected(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        response = self._generate_access_token(
            code, client_id=client_id, code_verifier='wrong-verifier',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_grant')

    def test_code_cannot_be_redeemed_twice(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)

        first_redeem_response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(first_redeem_response.status_code, 200)
        self.assertIn('access_token', first_redeem_response.json())
        second_redeem_response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(second_redeem_response.status_code, 400)
        self.assertEqual(second_redeem_response.json()['error'], 'invalid_grant')

    def test_redirect_uri_mismatch_at_token_is_rejected(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': f'{REDIRECT_URI}\nhttps://other.example.com/cb',
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id, redirect_uri=REDIRECT_URI)
        response = self._generate_access_token(
            code, client_id=client_id,
            redirect_uri='https://other.example.com/cb',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_grant')

    def test_loopback_redirect_uri_port_must_match_exactly_at_token(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': 'http://127.0.0.1:8080/cb'
        }).client_id
        self.authenticate('internal_user', 'internal_user')

        code = self._generate_auth_code(client_id=client_id, redirect_uri='http://127.0.0.1:54321/cb')
        response = self._generate_access_token(
            code, client_id=client_id,
            redirect_uri='http://127.0.0.1:9999/cb',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_grant')

        response = self._generate_access_token(
            code, client_id=client_id,
            redirect_uri='http://127.0.0.1:54321/cb',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access_token', response.json())

    def test_access_denied_at_redemption_if_the_user_is_no_longer_internal(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        self.internal_user.write({'group_ids': [Command.unlink(self.env.ref('base.group_user').id)]})

        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_grant')
        self.assertEqual(response.json()['error_description'], 'Only internal users are allowed to use oauth for mcp')

    def test_revoke_removes_the_access_token(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        access_token = self._generate_access_token(code, client_id=client_id).json()['access_token']

        revoke_response = self.url_open('/oauth/revoke', data={'token': access_token})
        self.assertEqual(revoke_response.status_code, 200)
        self.assertFalse(self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')]))
        self.assertIsNone(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=access_token))

    def test_revoke_reports_success_for_an_unknown_token(self):
        # RFC 7009: the caller must not be able to tell an unknown token from a revoked one.
        response = self.url_open('/oauth/revoke', data={'token': 'some-token'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {})

    def test_removing_the_apikey_rejects_the_access_token(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        access_token = self._generate_access_token(code, client_id=client_id).json()['access_token']

        apikey = self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')])
        apikey._remove()

        self.assertFalse(apikey.exists())
        self.assertIsNone(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=access_token))

    def test_single_client_can_generate_multiple_tokens_for_the_same_user(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')

        first_code = self._generate_auth_code(client_id=client_id)
        first_token = self._generate_access_token(first_code, client_id=client_id).json()['access_token']
        second_code = self._generate_auth_code(client_id=client_id)
        second_token = self._generate_access_token(second_code, client_id=client_id).json()['access_token']

        self.assertNotEqual(first_token, second_token)
        self.assertEqual(len(self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')])), 2)
        for access_token in (first_token, second_token):
            self.assertEqual(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=access_token), self.internal_user.id)

    def test_single_client_can_generate_tokens_for_several_users(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        other_user = new_test_user(self.env, login='other_internal_user', groups='base.group_user')

        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        first_user_token = self._generate_access_token(code, client_id=client_id).json()['access_token']

        self.authenticate('other_internal_user', 'other_internal_user')
        code = self._generate_auth_code(client_id=client_id)
        other_user_token = self._generate_access_token(code, client_id=client_id).json()['access_token']

        self.assertEqual(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=first_user_token), self.internal_user.id)
        self.assertEqual(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=other_user_token), other_user.id)

    def test_authorization_code_of_inactive_user_is_rejected(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)

        self.internal_user.active = False
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()['error'], 'invalid_grant')
        self.assertFalse(self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')]))

        self.internal_user.active = True
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=response.json()['access_token']), self.internal_user.id)

    def test_authorization_code_of_inactive_client_is_rejected(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id)
        client = self.env['oauth.client'].search([('client_id', '=', client_id)])

        client.action_archive()
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()['error'], 'invalid_client')
        self.assertFalse(self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')]))

        client.action_unarchive()
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.env['res.users.apikeys']._check_credentials(scope='mcp', key=response.json()['access_token']), self.internal_user.id)

    def test_consented_duration_sets_the_apikey_expiration_date(self):
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('regular_user', 'regular_user')

        code = self._generate_auth_code(client_id=client_id, duration='7')
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 200, response.text)

        expected_expiration_date = fields.Datetime.to_datetime(fields.Date.today() + timedelta(days=7))
        self.assertEqual(
            self.env['res.users.apikeys'].search([('user_id', '=', self.regular_user.id), ('scope', '=', 'mcp')]).expiration_date,
            expected_expiration_date,
        )
        self.assertEqual(
            response.json()['expires_in'],
            (expected_expiration_date - fields.Datetime.now()).total_seconds(),
        )

    def test_duration_beyond_the_user_privileges_is_rejected(self):
        # base.group_user_regular caps the API keys of a regular internal user at 90 days.
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('regular_user', 'regular_user')

        response = self._submit_consent(client_id=client_id, duration='365')
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()['error'], 'authorization_failed')
        self.assertEqual(response.json()['error_description'], 'You cannot exceed 90.0 days.')

    def test_duration_is_rechecked_when_the_code_is_redeemed(self):
        # The user consents to a year, then loses the privilege before the client redeems the code.
        self.env.ref('base.group_user').api_key_duration = 365
        client_id = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': REDIRECT_URI
        }).client_id
        self.authenticate('internal_user', 'internal_user')
        code = self._generate_auth_code(client_id=client_id, duration='365')

        self.env.ref('base.group_user').api_key_duration = 1
        response = self._generate_access_token(code, client_id=client_id)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()['error'], 'invalid_grant')
        self.assertEqual(response.json()['error_description'], 'You cannot exceed 1.0 days.')
        self.assertFalse(self.env['res.users.apikeys'].search([('user_id', '=', self.internal_user.id), ('scope', '=', 'mcp')]))
