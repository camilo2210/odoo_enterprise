from collections import defaultdict
from contextlib import contextmanager
from http import HTTPStatus
import re
from requests.exceptions import ConnectionError
from socket import AF_INET, IPPROTO_TCP, SOCK_STREAM
from unittest.mock import MagicMock, patch
import urllib.parse

from odoo import api
from odoo.fields import Domain
from odoo.http.dispatcher import serialize_exception
from odoo.tests import new_test_user
from odoo.tests.common import TransactionCase


class TestDatabasesCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensure the tests doesn't get disturbed by any data that would already present in the database
        pre_existing_project = cls.env['project.project'].search([])
        origin_search_fetch = cls.env.registry['project.project'].search_fetch

        @api.model
        def search_fetch(cls, domain, *args, **kwargs):
            return origin_search_fetch(cls, Domain.AND([domain, [('id', 'not in', pre_existing_project.ids)]]), *args, **kwargs)

        cls.startClassPatcher(patch.object(cls.env.registry["project.project"], "search_fetch", search_fetch))

        cls.user_employee = new_test_user(cls.env, login='employee@company.tld', groups="base.group_user")
        cls.user_db_user = new_test_user(cls.env, login='db_user@company.tld', groups="databases.group_databases_user")
        cls.user_db_manager = new_test_user(cls.env, login='db_manager@company.tld', groups="databases.group_databases_manager")
        cls.user_proj_user = new_test_user(cls.env, login='project_user@company.tld', groups="project.group_project_user")
        cls.user_proj_manager = new_test_user(cls.env, login='project_manager@company.tld', groups="project.group_project_manager")

        # Tell the database how to connect
        cls.env['ir.config_parameter'].set_str('databases.odoocom_apikey', 'odoocom_privateKey')

        cls.startClassPatcher(patch('odoo.addons.databases.wizard.databases_synchronization_wizard.getaddrinfo',
                                    return_value=[(AF_INET, SOCK_STREAM, IPPROTO_TCP, '', ('127.0.0.1', 0))]))

    def setUp(self):
        super().setUp()

        self.json2_mocked_calls = defaultdict(lambda: defaultdict(dict))

        def mock_requests_request(method, uri, *args, **kwargs):
            parsed_url = urllib.parse.urlparse(uri)

            if parsed_url.hostname not in self.json2_mocked_calls:
                raise ConnectionError(f'Could not connect to {parsed_url.hostname}')
            hostname_calls = self.json2_mocked_calls[parsed_url.hostname]

            # To handle /json/version, add a line like this in your test:
            # json2_mocked_calls[hostname]['version'] = '19.0+e'
            if parsed_url.path == '/json/version':
                self.assertEqual(method, 'get')
                if 'version' not in hostname_calls:
                    return MagicMock(status_code=HTTPStatus.SEE_OTHER)
                value = {
                    'version': hostname_calls['version'],
                    # 'version_info': ...,  # We should not rely on this field
                }
                return MagicMock(status_code=HTTPStatus.OK, **{'json.return_value': value})
            m = re.match(r'^/json/2/(?P<model>[^/]*)/(?P<method>[^/]*)$', parsed_url.path)
            self.assertTrue(m, f'{uri!r} is not a valid /json/2 route')
            self.assertEqual(method, 'post')

            model_name = m.group('model')
            self.assertIn(model_name, hostname_calls, f'No json2_mocked_calls defined for {parsed_url.hostname!r}/{model_name!r}')
            model = hostname_calls[model_name]

            method_name = m.group('method')
            self.assertIn(method_name, model)
            value = model[method_name]

            if isinstance(value, Exception):
                return MagicMock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, **{
                    'json.return_value': serialize_exception(value),
                })

            return MagicMock(status_code=HTTPStatus.OK, **{'json.return_value': value})

        self.mock_requests_request = self.startPatcher(
            patch("requests.api.request", side_effect=mock_requests_request))

    @contextmanager
    def capture_wizard(self):
        WizardType = self.env.registry['databases.synchronization.wizard']
        original_do_sync = WizardType._do_synchronize
        captured = {'wizards': []}

        def side_effect(self):
            captured['wizards'].append(self)
            return original_do_sync(self)

        with patch.object(WizardType, '_do_synchronize', side_effect=side_effect, autospec=True):
            yield captured
