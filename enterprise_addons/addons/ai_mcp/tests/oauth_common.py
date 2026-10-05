from urllib.parse import parse_qs, urlsplit

from odoo.tests import HttpCase, new_test_user

from odoo.addons.ai_mcp.utils.oauth_utils import challenge_from_verifier

REDIRECT_URI = 'https://client.example.com/callback'


class OauthServerCommon(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = new_test_user(cls.env, login='internal_user', groups='base.group_user')
        cls.regular_user = new_test_user(
            cls.env, login='regular_user', groups='base.group_user,base.group_user_regular',
        )
        cls.portal_user = new_test_user(cls.env, login='portal_user', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        # Client registrations are rate limited per source IP within a time window. The whole test
        # run shares one registry and one source IP, so each test has to start from a clean budget.
        if hasattr(self.env.registry, '_dcr_registration_requests'):
            del self.env.registry._dcr_registration_requests

    def _authorize(self, allow_redirects=True, **params_overrides):
        params = {
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'code_challenge': challenge_from_verifier(self._get_verifier()),
            'code_challenge_method': 'S256',
            'state': 'xyz',
            **params_overrides,
        }
        return self.url_open('/oauth/authorize', params=params, allow_redirects=allow_redirects)

    def _submit_consent(self, **params_overrides):
        params = {
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'code_challenge': challenge_from_verifier(self._get_verifier()),
            'code_challenge_method': 'S256',
            'state': 'xyz',
            'allow': 'true',
            'csrf_token': self.csrf_token(),
            'duration': '1',
            **params_overrides,
        }
        return self.url_open('/oauth/authorize/submit_consent', data=params, allow_redirects=False)

    def _generate_auth_code(self, **params_overrides):
        consent_response = self._submit_consent(**params_overrides)
        location = consent_response.headers['Location']
        return parse_qs(urlsplit(location).query)['code'][0]

    def _generate_access_token(self, code, **params_overrides):
        params = {
            'redirect_uri': REDIRECT_URI,
            'code_verifier': self._get_verifier(),
            'code': code,
            'grant_type': 'authorization_code',
            **params_overrides,
        }
        return self.url_open('/oauth/token', data=params)

    def _get_verifier(self):
        return 'a' * 64
