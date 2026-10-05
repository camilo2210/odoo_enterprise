from unittest.mock import MagicMock, patch

from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .common import TestAccountAvataxCommon, TestAvataxCommon
from odoo.addons.account_avatax.lib.avatax_client import AvataxClient

REGISTRATION_REQUESTS_PATH = 'odoo.addons.account_avatax.models.account_edi_proxy_user.requests'


def _mock_post_response(data):
    """Create a mock requests.Response returning the given data as JSON."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    return mock_resp


@tagged("-at_install", "post_install")
class TestAvataxIAPRouting(TestAccountAvataxCommon):
    """Test that AvataxClient methods correctly route through iap_request
    when connection_method is 'iap'."""
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.env.company.avalara_connection_method = 'iap'
        cls.env.company.avalara_iap_connected = True
        cls.config = cls.env['res.config.settings'].create({})
        return res

    def test_iap_ping(self):
        with self._capture_request(return_value={'authenticated': True}) as capture:
            client = AvataxClient._get_client(self.env.company)
            result = client.ping()
        self.assertIsNotNone(capture.val)
        self.assertTrue(result.get('authenticated'))

    def test_iap_get_companies(self):
        response = {'@recordsetCount': '1', 'value': [{'id': 1, 'name': 'Test'}]}
        with self._capture_request(return_value=response) as capture:
            client = AvataxClient._get_client(self.env.company)
            result = client.get_companies()
        self.assertIsNotNone(capture.val)
        self.assertEqual(result['@recordsetCount'], '1')

    def test_iap_list_nexus(self):
        response = {'@recordsetCount': '1', 'value': [{'jurisName': 'CALIFORNIA'}]}
        with self._capture_request(return_value=response) as capture:
            client = AvataxClient._get_client(self.env.company)
            result = client.list_nexus(1)
        self.assertIsNotNone(capture.val)
        self.assertEqual(result['value'][0]['jurisName'], 'CALIFORNIA')

    def test_iap_not_connected_fails_gracefully(self):
        """Included selected but not connected raises RedirectWarning; leftover Direct
        credentials don't silently make it look configured."""
        self.env.company.avalara_iap_connected = False
        self.assertTrue(self.env.company.avalara_api_id and self.env.company.avalara_api_key)
        with self.assertRaisesRegex(RedirectWarning, "Avalara Included"):
            AvataxClient._get_client(self.env.company)


@tagged("-at_install", "post_install")
class TestAvataxIAPPing(TestAvataxCommon):
    """Test the avatax_ping flow which exercises ping, get_companies, and list_nexus."""

    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.env.company.avalara_connection_method = 'iap'
        cls.env.company.avalara_iap_connected = True
        cls.config = cls.env['res.config.settings'].create({})
        return res

    def test_avatax_ping_with_nexus(self):
        """avatax_ping calls ping, get_companies, and list_nexus in sequence."""
        ping_response = {'authenticated': True, 'version': '1.0'}
        companies_response = {
            '@recordsetCount': '1',
            'value': [{'id': 12345, 'name': 'Test Company'}],
        }
        nexus_response = {
            '@recordsetCount': '6',
            'value': [
                # country-wide rows carry the country code as their region (not blank);
                # they're identified by jurisdictionTypeId and must be dropped.
                {'country': 'US', 'region': 'US', 'jurisName': 'UNITED STATES', 'jurisTypeId': 'CNT', 'jurisdictionTypeId': 'Country'},
                {'country': 'CA', 'region': 'CA', 'jurisName': 'CANADA', 'jurisTypeId': 'CNT', 'jurisdictionTypeId': 'Country'},
                {'country': 'US', 'region': 'CA', 'jurisName': 'CALIFORNIA', 'jurisTypeId': 'STA', 'jurisdictionTypeId': 'State'},
                # duplicate jurisdiction (a second tax-type group for the same state) is deduped
                {'country': 'US', 'region': 'CA', 'jurisName': 'CALIFORNIA', 'jurisTypeId': 'STA', 'jurisdictionTypeId': 'State', 'nexusTaxTypeGroup': 'EWaste'},
                {'country': 'US', 'region': 'NY', 'jurisName': 'NEW YORK', 'jurisTypeId': 'STA', 'jurisdictionTypeId': 'State'},
                {'country': 'CA', 'region': 'ON', 'jurisName': 'ONTARIO', 'jurisTypeId': 'STA', 'jurisdictionTypeId': 'State'},
            ],
        }

        call_count = 0

        def mock_capture(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ping_response
            if call_count == 2:
                return companies_response
            return nexus_response

        with self._capture_request(return_func=mock_capture):
            result = self.config.avatax_ping()

        self.assertEqual(result['res_model'], 'avatax.connection.test.result')
        self.assertEqual(call_count, 3, "Should have made 3 API calls: ping, get_companies, list_nexus")

        body = self.env['avatax.connection.test.result'].browse(result['res_id']).server_response
        self.assertIn('Nexus locations', body)
        self.assertIn('3 jurisdictions across 2 countries', body)
        # Grouped by country, deduped, with the country-wide row excluded from the count.
        self.assertIn('United States (2)', body)
        self.assertIn('California · New York', body)
        self.assertIn('Canada (1)', body)
        self.assertNotIn('· United States', body, "Country-wide nexus row should not be listed as a jurisdiction")

    def test_avatax_ping_no_companies(self):
        """avatax_ping skips list_nexus when no companies are returned."""
        ping_response = {'authenticated': True, 'version': '1.0'}
        companies_response = {'@recordsetCount': '0', 'value': []}

        call_count = 0

        def mock_capture(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ping_response
            return companies_response

        with self._capture_request(return_func=mock_capture):
            self.config.avatax_ping()

        self.assertEqual(call_count, 2, "Should have made 2 API calls: ping and get_companies only")

    def test_avatax_ping_no_nexus(self):
        """avatax_ping handles companies with no nexus locations."""
        ping_response = {'authenticated': True, 'version': '1.0'}
        companies_response = {
            '@recordsetCount': '1',
            'value': [{'id': 12345, 'name': 'Test Company'}],
        }
        nexus_response = {'@recordsetCount': '0', 'value': []}

        call_count = 0

        def mock_capture(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ping_response
            if call_count == 2:
                return companies_response
            return nexus_response

        with self._capture_request(return_func=mock_capture):
            result = self.config.avatax_ping()

        self.assertEqual(call_count, 3)
        popup = self.env['avatax.connection.test.result'].browse(result['res_id'])
        self.assertNotIn('Nexus', popup.server_response)


@tagged("-at_install", "post_install")
class TestAvataxMigrateToIAP(TestAvataxCommon):
    """Test the avatax_migrate_to_iap flow which exercises link_to_iap."""

    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.config = cls.env['res.config.settings'].create({})
        return res

    def setUp(self):
        super().setUp()
        # Clean up any proxy user from a previous test to avoid unique constraint violations.
        self.env['account_edi_proxy_client.user'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('proxy_type', '=', 'avatax'),
        ]).unlink()

    def test_migrate_to_iap_success(self):
        """Successful migration sets connection_method to 'iap' and creates proxy user."""
        self.env.company.avalara_connection_method = 'manual'
        response = {
            'id_client': 'test_id_client',
            'refresh_token': 'test_refresh_token',
            'authenticated': True,
            'Avalara Account #': 'AVALARA_LOGIN_ID',
            'message': 'Your Avalara Direct account has been successfully migrated '
                'to Avalara Included and linked to this database.',
        }
        with patch(f'{REGISTRATION_REQUESTS_PATH}.post', return_value=_mock_post_response(response)):
            result = self.config.avatax_migrate_to_iap()

        self.assertEqual(self.env.company.avalara_connection_method, 'iap')
        self.assertTrue(self.env.company.avalara_iap_connected)
        self.assertEqual(result['res_model'], 'avatax.connection.test.result')

        proxy_user = self.env['account_edi_proxy_client.user'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('proxy_type', '=', 'avatax'),
        ], limit=1)
        self.assertTrue(proxy_user)
        self.assertEqual(proxy_user.id_client, 'test_id_client')

    @mute_logger('odoo.addons.account_avatax.models.account_external_tax_mixin')
    def test_migrate_to_iap_avatax_error(self):
        """Avatax-level error raises UserError."""
        self.env.company.avalara_connection_method = 'manual'
        response = {
            'error': {
                'code': 'AuthenticationException',
                'message': 'Authentication failed.',
                'details': [{'description': 'The user or account could not be authenticated.'}],
            },
        }
        with patch(f'{REGISTRATION_REQUESTS_PATH}.post', return_value=_mock_post_response(response)):
            with self.assertRaisesRegex(UserError, 'could not be authenticated'):
                self.config.avatax_migrate_to_iap()

        self.assertEqual(self.env.company.avalara_connection_method, 'manual',
                         "Connection method should remain manual on error")

    @mute_logger('odoo.addons.account_avatax.models.account_external_tax_mixin')
    def test_migrate_to_iap_iap_http_error(self):
        """IAP HTTP-level error (e.g. invalid db_uuid) raises UserError."""
        self.env.company.avalara_connection_method = 'manual'
        response = {
            'errors': 'INVALID_DBUUID',
            'title': 'No valid enterprise contract!',
        }
        with patch(f'{REGISTRATION_REQUESTS_PATH}.post', return_value=_mock_post_response(response)):
            with self.assertRaisesRegex(UserError, 'enterprise contract'):
                self.config.avatax_migrate_to_iap()

        self.assertEqual(self.env.company.avalara_connection_method, 'manual')


@tagged("-at_install", "post_install")
class TestAvataxConnectToIAP(TestAvataxCommon):
    """Test the avatax_connect_to_iap flow and its pre-flight validations."""

    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.env.company.avalara_connection_method = 'iap'
        cls.config = cls.env['res.config.settings'].create({})
        return res

    def setUp(self):
        super().setUp()
        self.env['account_edi_proxy_client.user'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('proxy_type', '=', 'avatax'),
        ]).unlink()

    def test_connect_to_iap_no_email(self):
        """Raises ValidationError when no email is set."""
        self.config.avalara_account_email = False
        with self.assertRaisesRegex(ValidationError, 'contact email'):
            self.config.avatax_connect_to_iap()

    def test_connect_to_iap_incomplete_address(self):
        """Raises RedirectWarning when company address is incomplete."""
        self.config.avalara_account_email = 'test@example.com'
        partner = self.env.company.partner_id
        for field in ('street', 'city', 'zip'):
            original = partner[field]
            partner[field] = False
            with self.assertRaisesRegex(RedirectWarning, 'complete address'):
                self.config.avatax_connect_to_iap()
            partner[field] = original

    def test_connect_to_iap_success(self):
        """Successful connection sets connection_method, api_id, and creates proxy user."""
        self.config.avalara_account_email = 'test@example.com'
        response = {
            'id_client': 'test_id_client',
            'refresh_token': 'test_refresh_token',
            'authenticated': True,
            'Avalara Account #': 'NEW_ACCOUNT_123',
            'Nexus Locations': ['California', 'New York'],
            'message': 'This Avatax account has been successfully created '
                'and linked to your database',
        }
        with patch(f'{REGISTRATION_REQUESTS_PATH}.post', return_value=_mock_post_response(response)):
            result = self.config.avatax_connect_to_iap()

        self.assertEqual(self.env.company.avalara_api_id, 'NEW_ACCOUNT_123')
        self.assertEqual(self.env.company.avalara_connection_method, 'iap')
        self.assertTrue(self.env.company.avalara_iap_connected)
        self.assertEqual(result['res_model'], 'avatax.connection.test.result')

        proxy_user = self.env['account_edi_proxy_client.user'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('proxy_type', '=', 'avatax'),
        ], limit=1)
        self.assertTrue(proxy_user)
        self.assertEqual(proxy_user.proxy_type, 'avatax')

    @mute_logger('odoo.addons.account_avatax.models.account_external_tax_mixin')
    def test_connect_to_iap_avatax_error(self):
        """Avatax-level error raises UserError without changing company settings."""
        self.config.avalara_account_email = 'test@example.com'
        original_api_id = self.env.company.avalara_api_id
        response = {
            'error': {
                'code': 'AccountCreationError',
                'message': 'Could not create account',
                'details': [{'description': 'The account could not be created at this time.'}],
            },
        }
        with patch(f'{REGISTRATION_REQUESTS_PATH}.post', return_value=_mock_post_response(response)):
            with self.assertRaisesRegex(UserError, 'could not be created'):
                self.config.avatax_connect_to_iap()

        self.assertEqual(self.env.company.avalara_api_id, original_api_id,
                         "API ID should not change on error")

    @mute_logger('odoo.addons.account_avatax.models.account_external_tax_mixin')
    def test_connect_to_iap_iap_http_error(self):
        """IAP HTTP-level error (e.g. invalid db_uuid) raises UserError."""
        self.config.avalara_account_email = 'test@example.com'
        original_api_id = self.env.company.avalara_api_id
        response = {
            'errors': 'INVALID_DBUUID',
            'title': 'No valid enterprise contract!',
        }
        with patch(f'{REGISTRATION_REQUESTS_PATH}.post', return_value=_mock_post_response(response)):
            with self.assertRaisesRegex(UserError, 'enterprise contract'):
                self.config.avatax_connect_to_iap()

        self.assertEqual(self.env.company.avalara_api_id, original_api_id)
