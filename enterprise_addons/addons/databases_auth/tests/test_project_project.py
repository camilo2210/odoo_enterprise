from unittest.mock import patch

from odoo.tests import Like, tagged
from odoo.tests.common import users

from odoo.addons.databases.tests.test_project_project import TestProjectProject


@tagged('-at_install', 'post_install')
class TestDatabasesAuthConnect(TestProjectProject):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_bool('databases.saas_single_sign_on', True)
        cls.database.database_name = 'anotherdb'
        cls.database.database_api_login = 'someuser'
        cls.database.database_api_key = 'key'

    @users('db_user@company.tld')
    def test_action_database_connect_saas_sso_first_time(self):
        action = self.database.with_user(self.env.user).action_database_connect()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': Like(
                'https://accounts.odoo.com/oauth2/auth?'
                'response_type=token&'
                'client_id=...&'
                'redirect_uri=...databases...auth...&'
                'scope=userinfo&'
                'state=...'
            ),
            'target': 'new',
        })

    @users('db_user@company.tld')
    @patch('odoo.addons.databases.api.OdooDatabaseApi.set_user_oauth')
    @patch('requests.sessions.Session.request')
    def test_action_database_connect_saas_sso_already_set(self, mock_request, mock_odoo_database_api):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = 'the_database_uuid'

        self.env.user.databases_sso_uid = '42'
        action = self.database.with_user(self.env.user).action_database_connect()
        mock_odoo_database_api.assert_called_once()  # Ensure we try to setup a smooth connection for the user
        mock_request.assert_called_once()
        self.assertEqual(action, {
            'type': 'ir.actions.act_url',
            'url': 'https://www.odoo.com/my/databases/connect/the_database_uuid',
            'target': 'new',
        })
