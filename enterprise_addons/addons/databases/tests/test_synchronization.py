from unittest.mock import call, MagicMock, patch
from socket import gaierror
import urllib.parse

from .common import TestDatabasesCommon

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tools.mail import html2plaintext
from odoo.tests import freeze_time, tagged
from odoo.tests.common import users
from odoo.addons.databases.models.project_project import get_database_api_keys


@tagged('-at_install', 'post_install')
class TestSynchronization(TestDatabasesCommon):

    def mock_json2_calls_for_db(self, fqdn, version='dont-write-it-to-project', users=[], kpis=[]):
        self.json2_mocked_calls[fqdn]['version'] = version
        self.json2_mocked_calls[fqdn]['res.users']['search_read'] = users
        self.json2_mocked_calls[fqdn]['res.users.apikeys']['generate'] = 'newApiKey'
        self.json2_mocked_calls[fqdn]['kpi.provider']['get_kpi_summary'] = kpis

    @users('db_manager@company.tld')
    def test_synchronization_disabled(self):
        self.env['ir.config_parameter'].sudo().set_str('databases.odoocom_apikey', None)

        self.env['project.project'].action_synchronize_all_databases()

        self.mock_requests_request.authenticate.assert_not_called()
        self.mock_requests_request.execute_kw.assert_not_called()

    @users('db_manager@company.tld')
    def test_synchronize_databases(self):
        """Synchronize the databases from the Odoo.com SaaS"""
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        new_projects = Project.search([])

        self.assertCountEqual(self.mock_requests_request.mock_calls[:1], [
            call('post', 'https://www.odoo.com/json/2/odoo.database/list', data=None, json={},
                 headers={'Authorization': 'Bearer odoocom_privateKey', 'X-Odoo-Database': 'openerp'}, allow_redirects=False, timeout=15),
        ])
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

        # Already-seen database update the project, based on the URL
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'Odoo', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'other_user@odoo.com', 'version': '17.0+e'},
        ]
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()
        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'Odoo',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
        ])

        wizard, = captured['wizards']
        self.assertEqual(wizard.summary_message, "0 new databases, 1 updated.")

    @users('db_user@company.tld')
    def test_synchronize_database_with_db_user(self):
        """
        - 1) Synchronize all db as databases_admin with a new db listed on odoo.com, with 'db_user@company.tld' user in it
           -> The database project should have been created
           -> a database user 'db_user@company.tld' should have been created
        - 2) Synchronize all db as databases_user with a new document kpi (and still report the same user)
          -> The kpi should have been updated correctly
        - 3) Synchronize all db as databases_user with a user deleted and a different kpi
          -> It should delete the user if the databases_user isn't in the list anymore
        """
        # 1) Synchronize all db as databases_admin with a new db listed on odoo.com
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'Odoo', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'other_user@odoo.com', 'version': '17.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', users=[{
            'id': 3, 'name': 'db_user@company.tld', 'login': 'db_user@company.tld', 'login_date': '2026-03-24 17:02:44',
        }])
        self.env['project.project'].with_user(self.user_db_manager).action_synchronize_all_databases()
        self.assertEqual(
            self.env['project.project'].search([]).database_user_ids.mapped('login'),
            ['db_user@company.tld'],
            "a database user 'db_user@company.tld' should have been created",
        )

        # 2) Synchronize all db as databases_user with a new document kpi (and still report the same user)
        self.mock_json2_calls_for_db(
            'odoo-sa.my.odoo.test',
            kpis=[{'id': 'documents.inbox', 'name': 'Inbox', 'type': 'integer', 'value': 10}],
            users=[{'id': 3, 'name': 'db_user@company.tld', 'login': 'db_user@company.tld', 'login_date': '2026-03-24 17:02:44'}],
        )
        self.env['project.project'].action_synchronize_all_databases()
        self.assertEqual(
            self.env['project.project'].search([]).database_nb_documents,
            10,
            "The kpi should have been updated correctly",
        )

        # 3) Synchronize all db as databases_user with a user deleted and a different kpi
        self.mock_json2_calls_for_db(
            'odoo-sa.my.odoo.test',
            kpis=[{'id': 'documents.inbox', 'name': 'Inbox', 'type': 'integer', 'value': 20}],
            users=[]  # Simulate user deletion from the remote db
        )
        self.env['project.project'].action_synchronize_all_databases()
        self.assertFalse(self.env['project.project'].search([]), 'db_user should have lost access')
        project = self.env['project.project'].sudo().search([])
        self.assertTrue(project, 'The database should still exist')
        self.assertFalse(project.database_user_ids, 'The database_user should have been deleted')
        self.assertEqual(project.database_nb_documents, 20, "The kpi should have been updated correctly")

    @users('db_manager@company.tld')
    def test_db_synchronize_several_dbs(self):
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
            {'name': 'titi-sarl', 'url': 'http://titi-sarl.my.odoo.test', 'login': 'admin@titi-sarl.fr', 'version': '17.0+e'},
            {'name': 'toto-nv', 'url': 'http://toto-nv.my.odoo.test', 'login': 'contact@toto-nv.be', 'version': '18.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        self.mock_json2_calls_for_db('titi-sarl.my.odoo.test')
        self.mock_json2_calls_for_db('toto-nv.my.odoo.test')
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()

        wizard, = captured['wizards']
        self.assertEqual(wizard.summary_message, "3 new databases, 3 updated.")

        self.assertCountEqual(self.mock_requests_request.mock_calls[:1], [
            call('post', 'https://www.odoo.com/json/2/odoo.database/list', data=None, json={},
                 headers={'Authorization': 'Bearer odoocom_privateKey', 'X-Odoo-Database': 'openerp'}, allow_redirects=False, timeout=15),
        ])
        new_projects = Project.search([], order='database_version')
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

        # Already-seen database update the project, based on the URL
        # Other dbs should stay untouched
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'Odoo', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'other_user@odoo.com', 'version': '17.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()
        wizard, = captured['wizards']
        self.assertEqual(wizard.summary_message, "0 new databases, 3 updated.")

        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'Odoo',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

    def test_odoocom_db_synchronization(self):
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'cron-odoo-sa', 'url': 'http://cron-odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['version'] = '16.0+e'
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['res.users']['search_read'] = []
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['res.users.apikeys']['generate'] = 'some_new_api_key'
        self.json2_mocked_calls['cron-odoo-sa.my.odoo.test']['kpi.provider']['get_kpi_summary'] = []

        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases_with_odoocom()
        new_projects = Project.search([])

        self.assertCountEqual(self.mock_requests_request.mock_calls, [
            call('post', 'https://www.odoo.com/json/2/odoo.database/list', data=None, json={},
                 headers={'Authorization': 'Bearer odoocom_privateKey', 'X-Odoo-Database': 'openerp'}, allow_redirects=False, timeout=15),
            call('post', 'http://cron-odoo-sa.my.odoo.test/json/2/res.users.apikeys/generate', data=None, json={
                    'key': 'odoocom_privateKey',
                    'scope': 'rpc',
                    'name': f'Access for {self.env.ref("base.main_company").name}',
                    'expiration_date': False,
                 },
                 headers={'Authorization': 'Bearer odoocom_privateKey', 'X-Odoo-Database': 'cron-odoo-sa'}, allow_redirects=False, timeout=15),
        ])
        self.assertRecordValues(new_projects, [
            {
                'name': 'cron-odoo-sa',
                'database_name': 'cron-odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://cron-odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
                'database_last_synchro': False,
            },
        ])

        database_api_key = get_database_api_keys(new_projects).get(new_projects.id)
        self.assertEqual(database_api_key, 'some_new_api_key')

        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database should now have been scanned",
        )

        with freeze_time('2025-01-01 23:59'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database shouldn't have been scanned yet",
        )

        with freeze_time('2025-01-02 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-02 00:00"),
            "The database should have been scanned",
        )

    def test_synchronizing_a_saas_db_with_just_a_url_should_raise_an_error(self):
        """ Trying to synchronize one single database missing a db name should raise a User Friendly error"""
        db_as_db_manager = self.env['project.project'].with_user(self.user_db_manager).create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://anotherdb.that.doesnt.exist',
            'database_user_ids': [Command.create({
                'name': 'db_user@company.tld',
                'login': 'db_user@company.tld',
            })]
        }])
        db_as_db_user = db_as_db_manager.with_user(self.user_db_user)
        # We don't want to use assertRaisesRegex because we don't want to rollback (simulate the commit)
        try:
            db_as_db_user.action_database_synchronize()
            self.fail("Should raise a UserError before")
        except UserError as e:
            self.assertIn("1 databases could not be synchronized.", str(e))
        self.assertRecordValues(db_as_db_user.message_ids, [
            {'preview': 'Error while connecting to http://anotherdb.that.doesnt.exist: '
                        'We are missing the database name, the api login or the api key'},
            {'preview': 'Project created'},
        ])
        self.assertIn('Unreachable', db_as_db_user.tag_ids.mapped('name'))

    @users('db_manager@company.tld')
    def test_synchronizing_several_db_with_one_missing_its_name_and_api_info(self):
        """ In case several db gets synchronized, it shouldn't raise an Error but show it later on in the wizard

            - Create a fully legit db record by synchronizing all dbs with Odoo.com
            - Create manually a db missing its name and credentials
            - Try to synchronize both db at the same time
            => No error raised
            => Any issue should be reported in the wizard
        """
        # gets one legit database created through odoo.com synchronization and sync it
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        anotherdb = Project.create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://anotherdb.that.doesnt.exist',
        }])
        dbs = Project.search([])
        self.assertEqual(len(dbs), 2)
        # Synchronizing several db shouldn't raise any error
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['version'] = '16.0+e'
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['search_read'] = []
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['kpi.provider']['get_kpi_summary'] = []
        with self.capture_wizard() as captured:
            dbs.action_database_synchronize()
        wizard, = captured['wizards']
        self.assertEqual(wizard.error_message.strip(), "1 databases could not be synchronized.")
        self.assertRecordValues(anotherdb.message_ids, [
            {'preview': 'Error while connecting to http://anotherdb.that.doesnt.exist: '
                        'We are missing the database name, the api login or the api key'},
            {'preview': 'Project created'},
        ])
        self.assertIn('Unreachable', anotherdb.tag_ids.mapped('name'))

    @users('db_manager@company.tld')
    def test_successful_synchronization_clears_unreachable_tag(self):
        Project = self.env['project.project']
        db = Project.create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://somedb.my.odoo.test',
            'database_name': 'somedb',
            'database_api_login': 'user',
            'database_api_key': 'key',
            'tag_ids': self.env.ref('databases.project_tag_db_unreachable').ids,
        }])
        self.mock_json2_calls_for_db('somedb.my.odoo.test')

        db.action_database_synchronize()

        self.assertNotIn('Unreachable', db.tag_ids.mapped('name'))

    @users('db_manager@company.tld')
    def test_synchronizing_all_databases_shouldnt_raise_but_should_report_any_issue(self):
        """ In case several db gets synchronized, it shouldn't raise an Error but show it later on in the wizard

            - Create manually a db missing its name and credentials
            - Synchronize everything, creating a new db record from sync
            => The db synced from odoo.com should be there
            => Any issue should be reported in the wizard
        """
        Project = self.env['project.project']
        anotherdb = Project.create([{
            'name': 'An accounting DB',
            'database_hosting': 'saas',
            'database_url': 'http://anotherdb.that.doesnt.exist',
        }])
        dbs = Project.search([])
        self.assertEqual(len(dbs), 1)

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
            {'name': 'erroneous', 'url': 'http://erroneous.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '18.0+e'},
        ]

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', version='saas~18.3a1+e')
        self.mock_json2_calls_for_db('erroneous.my.odoo.test', version='saas~18.1+e',
                                     users=UserError('Getting users error message'),
                                     kpis=UserError('Getting KPIs error message'))

        # This shouldn't raise any error
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()
        dbs = Project.search([])
        self.assertRecordValues(dbs, [{
            'database_url': 'http://anotherdb.that.doesnt.exist',
            'database_version': False,
        }, {
            'database_url': 'http://erroneous.my.odoo.test',
            'database_version': 'saas~18.1',
        }, {
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_version': 'saas~18.3',
        }])

        wizard, = captured['wizards']
        self.assertEqual(wizard.error_message.strip(), "2 databases could not be synchronized.")

        self.assertRecordValues(anotherdb.message_ids, [
            {'preview': 'Error while connecting to http://anotherdb.that.doesnt.exist: '
                            'We are missing the database name, the api login or the api key'},
            {'preview': 'Project created'},
        ])
        self.assertIn('Unreachable', anotherdb.tag_ids.mapped('name'))

        erroneousdb = Project.search([('database_name', '=', 'erroneous')])
        self.assertEqual(html2plaintext(erroneousdb.message_ids[0].body),
                         'Error while getting users from erroneous: Getting users error message\n'
                         'Error while getting KPIs from erroneous: Getting KPIs error message')
        self.assertIn('Unreachable', erroneousdb.tag_ids.mapped('name'))

    @users('db_manager@company.tld')
    def test_synchronizing_all_databases_shouldnt_raise_due_to_dns_errors(self):
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        mock_gai = self.startPatcher(patch("odoo.addons.databases.wizard.databases_synchronization_wizard.getaddrinfo",
                                           side_effect=gaierror("some getaddrinfo error")))

        Project.action_synchronize_all_databases()
        dbs = Project.search([])
        self.assertRecordValues(dbs.message_ids, [
            {'preview': 'Error while resolving http://odoo-sa.my.odoo.test: some getaddrinfo error'},
            {'preview': 'Project created from template Database Template.'},
            {'preview': 'Project created'},
        ])

        mock_gai.configure_mock(side_effect=None, return_value=[])

        Project.action_synchronize_all_databases()
        self.assertRecordValues(dbs.message_ids, [
            {'preview': 'Error while resolving http://odoo-sa.my.odoo.test: found no IP'},
            {'preview': 'Error while resolving http://odoo-sa.my.odoo.test: some getaddrinfo error'},
            {'preview': 'Project created from template Database Template.'},
            {'preview': 'Project created'},
        ])

    @users('db_manager@company.tld')
    def test_synchronizing_all_databases_shouldnt_raise_if_project_template_not_configured(self):
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.env['ir.config_parameter'].sudo().set_int('databases.odoocom_project_template', None)

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        # This shouldn't raise any error
        self.env['project.project'].action_synchronize_all_databases()

    @users('db_manager@company.tld')
    def test_sync_pull_db_record_already_registered_as_saas_manually(self):
        """ If a db was manually created as a saas db and synchronized later on, the information should be udpated
            - Manually Create a saas db record with missing informations
            - Trigger the synchronization
            => The db informations should be updated
        """
        Project = self.env['project.project']
        self.assertFalse(Project.search([]), "There shouldn't be any project yet")
        Project.create([{
            'name': 'odoo-sa',
            'database_hosting': 'saas',
            'database_url': 'http://odoo-sa.my.odoo.test',
        }])
        db = Project.search([])
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': False,
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': False,
                'database_version': False,
            },
        ])

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

    @users('db_manager@company.tld')
    def test_db_on_premise_configured_shouldnt_be_modified(self):
        """ Fully configured on premise Db reported by odoo.com shouldn't be updated as it could wrongly override
            the data and be very frustrating to the db manager.
            - Manually create an on premise db
            - configure the login and apikey
            - update all dbs
            => The database should have been left untouched
        """
        Project = self.env['project.project']
        self.assertFalse(Project.search([]), "There shouldn't be any project yet")
        Project.create([{
            'name': 'odoo-sa',
            'database_hosting': 'premise',
            'database_name': 'odoo-sa',
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_api_login': 'randomlogin@randomdomain.random',
            'database_api_key': 'random api key, amazing',
        }])
        db = Project.search([])
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'premise',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'randomlogin@randomdomain.random',
            },
        ])
        database_api_key = get_database_api_keys(db).get(db.id)
        self.assertEqual(database_api_key, 'random api key, amazing')

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'somethingelse@wout.wout', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'premise',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'randomlogin@randomdomain.random',
                'database_version': False,
            },
        ])
        database_api_key = get_database_api_keys(db).get(db.id)
        self.assertEqual(database_api_key, 'random api key, amazing')
        wizard, = captured['wizards']
        self.assertFalse(wizard.error_message)
        self.assertRecordValues(db.message_ids, [{'preview': 'Project created'}])
        self.assertNotIn('Unreachable', db.tag_ids.mapped('name'))

    @users('db_manager@company.tld')
    def test_db_on_premise_not_configured_should_be_updated_to_saas_db(self):
        """ A NOT configured on premise Db reported by odoo.com should be updated with odoo.com data
            - Manually create an on premise db
            - update all dbs
            => The database should have been updated and be reported as a saas databases
        """
        Project = self.env['project.project']
        self.assertFalse(Project.search([]), "There shouldn't be any project yet")
        Project.create([{
            'name': 'odoo-sa',
            'database_hosting': 'premise',
            'database_url': 'http://odoo-sa.my.odoo.test',
        }])
        db = Project.search([])
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': False,
                'database_hosting': 'premise',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': False,
                'database_version': False,
            },
        ])

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test')
        Project.action_synchronize_all_databases()
        self.assertRecordValues(db, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_without_configuration(self):
        self.env['ir.config_parameter'].sudo().set_str('databases.odoocom_apikey', None)

        wizard = self.env['databases.synchronization.wizard'].create({})

        # This shouldn't raise any error
        wizard._do_update_from_odoocom()

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_with_authenticate_error(self):
        # Simulate an invalid API key error
        self.mock_requests_request.configure_mock(**{
            'side_effect': None,
            'return_value.status_code': 401,
            'return_value.json.return_value': {'message': 'Invalid apikey'},
        })

        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()
        self.assertEqual(wizard.error_message, 'Error while listing databases from https://www.odoo.com: Invalid apikey\n')

    @users('db_manager@company.tld')
    def test_synchronization_wizard_update_from_odoocom_with_call_error(self):
        # Simulate an exception
        self.mock_requests_request.configure_mock(**{
            'side_effect': None,
            'return_value.status_code': 422,
            'return_value.json.return_value': {'message': 'Some error'},
        })

        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()
        self.assertEqual(wizard.error_message, 'Error while listing databases from https://www.odoo.com: Some error\n')

    @users('db_manager@company.tld')
    def test_user_management(self):
        database = self.env['project.project'].create([{
            'name': 'odoo-sa',
            'database_hosting': 'saas',
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_name': 'odoo-sa',
            'database_api_login': 'admin',
            'database_api_key': 'admin_apikey',
        }])
        invite_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'invite',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })

        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['web_create_users'] = True
        invite_wizard.action_invite_users()
        self.assertCountEqual(self.mock_requests_request.mock_calls, [
            call('post', 'http://odoo-sa.my.odoo.test/json/2/res.users/web_create_users', data=None, json={
                'emails': ['employee@company.tld'],
                'context': {'no_reset_password': True},
            }, headers={'Authorization': 'Bearer admin_apikey', 'X-Odoo-Database': 'odoo-sa'}, allow_redirects=False, timeout=15),
        ])
        self.assertFalse(invite_wizard.error_message)

        self.mock_requests_request.reset_mock()
        remove_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'remove',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['search'] = [23]
        self.json2_mocked_calls['odoo-sa.my.odoo.test']['res.users']['write'] = True
        invite_wizard.action_remove_users()
        self.assertCountEqual(self.mock_requests_request.mock_calls, [
            call('post', 'http://odoo-sa.my.odoo.test/json/2/res.users/search', data=None, json={
                'domain': [('login', 'in', ['employee@company.tld'])],
            }, headers={'Authorization': 'Bearer admin_apikey', 'X-Odoo-Database': 'odoo-sa'}, allow_redirects=False, timeout=15),
            call('post', 'http://odoo-sa.my.odoo.test/json/2/res.users/write', data=None, json={
                'ids': [23],
                'vals': {'active': False},
            }, headers={'Authorization': 'Bearer admin_apikey', 'X-Odoo-Database': 'odoo-sa'}, allow_redirects=False, timeout=15),
        ])

        self.assertFalse(remove_wizard.error_message)

    @users('db_manager@company.tld')
    def test_synchronization_with_duplicate_property_labels(self):
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', kpis=[
            {'id': 'my_kpi.some_unique_id', 'name': 'Duplicate label', 'type': 'integer', 'value': 1},
            {'id': 'my_kpi.another_unique_id', 'name': 'Duplicate label', 'type': 'integer', 'value': 4},
        ])
        Project.action_synchronize_all_databases()
        new_projects = Project.search([])

        self.assertRecordValues(new_projects.sudo().database_kpi_base_definition_id, [{
            'properties_definition': [
                {'name': 'my_kpi_some_unique_id', 'string': 'Duplicate label', 'type': 'integer', 'default': 0},
                {'name': 'my_kpi_another_unique_id', 'string': 'Duplicate label', 'type': 'integer', 'default': 0},
            ],
        }])
        self.assertRecordValues(new_projects, [{
            'database_kpi_properties': {
                'my_kpi_some_unique_id': 1,
                'my_kpi_another_unique_id': 4,
            },
        }])

    @users('db_manager@company.tld')
    def test_synchronization_applies_latest_kpi_snapshot(self):
        Project = self.env['project.project']
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = [
            {'name': 'odoo-sa', 'url': 'http://odoo-sa.my.odoo.test', 'login': 'some_user@odoo.com', 'version': '16.0+e'},
        ]
        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', kpis=[
            {'id': 'my_kpi.mon_bel_id', 'name': 'My KPI', 'type': 'integer', 'value': 1},
            {'id': 'my_kpi.mon_autre_bel_id', 'name': 'My other KPI', 'type': 'integer', 'value': 2},
        ])
        Project.action_synchronize_all_databases()
        new_projects = Project.search([])

        self.assertRecordValues(new_projects.sudo().database_kpi_base_definition_id, [{
            'properties_definition': [
                {'name': 'my_kpi_mon_bel_id', 'string': 'My KPI', 'type': 'integer', 'default': 0},
                {'name': 'my_kpi_mon_autre_bel_id', 'string': 'My other KPI', 'type': 'integer', 'default': 0},
            ],
        }])
        self.assertRecordValues(
            new_projects,
            [{
                "database_kpi_properties": {
                    "my_kpi_mon_bel_id": 1,
                    "my_kpi_mon_autre_bel_id": 2,
                }
            }],
        )

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', kpis=[
            {'id': 'my_kpi.mon_bel_id', 'name': 'My KPI', 'type': 'integer', 'value': 0},
            {'id': 'my_kpi.mon_autre_bel_id', 'name': 'My KPI', 'type': 'integer', 'value': 1},
        ])
        Project.action_synchronize_all_databases()
        self.assertRecordValues(new_projects, [{'database_kpi_properties': {'my_kpi_mon_bel_id': 0, 'my_kpi_mon_autre_bel_id': 1}}])

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', kpis=[
            {'id': 'my_kpi.mon_autre_bel_id', 'name': 'My KPI', 'type': 'integer', 'value': 0},
        ])
        Project.action_synchronize_all_databases()
        self.assertRecordValues(new_projects, [{'database_kpi_properties': {'my_kpi_mon_autre_bel_id': 0}}])

        self.mock_json2_calls_for_db('odoo-sa.my.odoo.test', kpis=[])
        Project.action_synchronize_all_databases()
        self.assertRecordValues(new_projects, [{'database_kpi_properties': {}}])

    @users('db_manager@company.tld')
    def test_synchronize_all_databases_synchronization_order(self):
        """Synchronizing all dbs should synchronize db from the user triggering the action first"""
        # set the synchronization limit to 1
        self.env['ir.config_parameter'].sudo().set_int('databases.immediate_sync_limit', 1)

        # create 2 db records, 1 in which the user has a login record, another one without
        db_other, db_user = self.env['project.project'].create([
            {
                'name': 'Other DB',
                'database_hosting': 'saas',
                'database_url': 'http://other-db.odoo.test',
                'database_name': 'other-db',
                'database_api_login': 'admin',
                'database_api_key': 'key',
            },
            {
                'name': 'User DB',
                'database_hosting': 'saas',
                'database_url': 'http://user-db.odoo.test',
                'database_name': 'user-db',
                'database_api_login': 'admin',
                'database_api_key': 'key',
                'database_user_ids': [Command.create({
                    'name': self.env.user.name,
                    'login': self.env.user.login,
                })]
            },
        ])

        # call action_synchronize_all_databases
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = []
        self.mock_json2_calls_for_db('user-db.odoo.test')
        self.mock_json2_calls_for_db('other-db.odoo.test')

        self.env['project.project'].action_synchronize_all_databases()

        # Ensure the db from the user was synchronized and that the other wasn't synchronized
        self.assertTrue(db_user.database_last_synchro, "The db in which the user can login should get synchronized first")
        self.assertFalse(
            db_other.database_last_synchro,
            "Considering that only one db can be synchronized right now, the db without a user should have been delayed."
        )

    @users('db_manager@company.tld')
    def test_synchronize_several_selected_databases_synchronization_order(self):
        """Synchronizing a selection of dbs should synchronize selected dbs in which the user can loggin first"""
        # set the synchronization limit to 1
        self.env['ir.config_parameter'].sudo().set_int('databases.immediate_sync_limit', 1)

        # create 3 db records, 2 in which the user has a login record, another one without
        db_user_1, db_other, db_user_2 = self.env['project.project'].create([
            {
                'name': 'User DB 1',
                'database_hosting': 'saas',
                'database_url': 'http://user-db-1.odoo.test',
                'database_name': 'user-db-1',
                'database_api_login': 'admin',
                'database_api_key': 'key',
                'database_user_ids': [Command.create({
                    'name': self.env.user.name,
                    'login': self.env.user.login,
                })]
            },
            {
                'name': 'Other DB',
                'database_hosting': 'saas',
                'database_url': 'http://other-db.odoo.test',
                'database_name': 'other-db',
                'database_api_login': 'admin',
                'database_api_key': 'key',
            },
            {
                'name': 'User DB 2',
                'database_hosting': 'saas',
                'database_url': 'http://user-db-2.odoo.test',
                'database_name': 'user-db-2',
                'database_api_login': 'admin',
                'database_api_key': 'key',
                'database_user_ids': [Command.create({
                    'name': self.env.user.name,
                    'login': self.env.user.login,
                })]
            }
        ])

        # select 1 db with a login and another one without and call action_database_synchronize on those
        selected_dbs = db_other + db_user_2
        self.mock_json2_calls_for_db('user-db-1.odoo.test')
        self.mock_json2_calls_for_db('user-db-2.odoo.test')
        self.mock_json2_calls_for_db('other-db.odoo.test')
        selected_dbs.action_database_synchronize()

        self.assertFalse(db_user_1.database_last_synchro, "This db wasn't selected and shouldn't have been synchronized")
        self.assertTrue(
            db_user_2.database_last_synchro,
            "This db is selected + the user can log in and thus should have been synchronized first"
        )
        self.assertFalse(
            db_other.database_last_synchro,
            "This db is selected but doesn't contain the user and should have been delayed"
        )

    @users('db_manager@company.tld')
    def test_ensuring_synchronization_order_change_depending_on_user(self):
        """This test ensure the sync order really changes depending on the user being in the databases"""
        # set the synchronization limit to 1
        self.env['ir.config_parameter'].sudo().set_int('databases.immediate_sync_limit', 1)

        # first ensure the databases are sync by id
        db_first_sync, db_second_sync = self.env['project.project'].create([
            {
                'name': 'Other DB',
                'database_hosting': 'saas',
                'database_url': 'http://other-db.odoo.test',
                'database_name': 'other-db',
                'database_api_login': 'admin',
                'database_api_key': 'key',
            },
            {
                'name': 'User DB',
                'database_hosting': 'saas',
                'database_url': 'http://another-db.odoo.test',
                'database_name': 'user-db',
                'database_api_login': 'admin',
                'database_api_key': 'key',
            },
        ])
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = []
        self.mock_json2_calls_for_db('user-db.odoo.test')
        self.mock_json2_calls_for_db('other-db.odoo.test')

        self.env['project.project'].action_synchronize_all_databases()

        self.assertTrue(db_first_sync.database_last_synchro, "This db should have been synchronized considering the default order")
        self.assertFalse(
            db_second_sync.database_last_synchro,
            "This db synchronization should have been delayed considering the default order"
        )

        # Synchronize a second time and ensure the second db was synchronized
        self.env['project.project'].action_synchronize_all_databases()

        # ensure second sync will sync this one
        self.assertTrue(db_second_sync.database_last_synchro, "The second synchronization should have synchronize this db first")

        # reset sync date, add a user and ensure it impacts the sync order
        dbs = (db_first_sync + db_second_sync)
        dbs.database_last_synchro = False
        self.assertFalse(any(dbs.mapped('database_last_synchro')))

        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = []
        self.mock_json2_calls_for_db('user-db.odoo.test')
        self.mock_json2_calls_for_db('other-db.odoo.test')
        db_second_sync.write({
            'database_user_ids': [Command.create({
                'name': self.env.user.name,
                'login': self.env.user.login,
            })]
        })

        self.env['project.project'].action_synchronize_all_databases()
        self.assertTrue(
            db_second_sync.database_last_synchro,
            "The user can log into this db and thus it should have been synchronized first"
        )
        self.assertFalse(
            db_first_sync.database_last_synchro,
            "This db synchronization should have been delayed considering only one db can be synchronized"
        )


@tagged('-at_install', 'post_install')
class TestXmlRpcSynchronization(TestDatabasesCommon):

    def setUp(self):
        super().setUp()

        # Simulate a server where /json/2 is not implemented, but let calls to odoo.com pass through
        def mock_requests_request(method, uri, *args, **kwargs):
            if urllib.parse.urlparse(uri).hostname == 'www.odoo.com':
                return prev_mock_requests_request(method, uri, *args, **kwargs)
            return MagicMock(status_code=303)

        prev_mock_requests_request = self.mock_requests_request.side_effect
        self.mock_requests_request.configure_mock(side_effect=mock_requests_request)

        # Return a specific mock object for each ServerProxy
        self.odoo_sa_xmrpc_common = MagicMock(**{'authenticate.return_value': -128})
        self.odoo_sa_xmrpc_object = MagicMock()
        self.call_resolution_per_uri = {
            "http://odoo-sa.my.odoo.test/xmlrpc/2/common": self.odoo_sa_xmrpc_common,
            "http://odoo-sa.my.odoo.test/xmlrpc/2/object": self.odoo_sa_xmrpc_object,
        }
        self.startPatcher(patch("xmlrpc.client.ServerProxy", side_effect=lambda uri: self.call_resolution_per_uri[uri]))

    def set_returned_databases_list(self, databases_list):
        for database in databases_list:
            self.call_resolution_per_uri.setdefault(f"{database['url']}/xmlrpc/2/common", MagicMock())\
                    .version.configure_mock(return_value={'server_serie': database['version']})
            self.call_resolution_per_uri.setdefault(f"{database['url']}/xmlrpc/2/object", MagicMock())
        self.json2_mocked_calls['www.odoo.com']['odoo.database']['list'] = databases_list

    @users('db_manager@company.tld')
    def test_synchronize_databases(self):
        """Synchronize the databases from the Odoo.com SaaS"""
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.set_returned_databases_list([
            {'name': 'odoo-sa', 'login': 'some_user@odoo.com', 'version': '16.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
        ])
        Project.action_synchronize_all_databases()
        new_projects = Project.search([])

        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
        ])

        # Already-seen database updates the project, based on the URL
        self.set_returned_databases_list([
            {'name': 'odoo-bis', 'login': 'other_user@odoo.com', 'version': '17.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
        ])
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()
        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-bis',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
        ])

        wizard, = captured['wizards']
        self.assertEqual(wizard.summary_message, "0 new databases, 1 updated.")

    @users('db_manager@company.tld')
    def test_db_synchronize_several_dbs(self):
        Project = self.env['project.project']
        self.set_returned_databases_list([
            {'name': 'odoo-sa', 'login': 'some_user@odoo.com', 'version': '16.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
            {'name': 'titi-sarl', 'login': 'admin@titi-sarl.fr', 'version': '17.0+e', 'url': 'http://titi-sarl.my.odoo.test'},
            {'name': 'toto-nv', 'login': 'contact@toto-nv.be', 'version': '18.0+e', 'url': 'http://toto-nv.my.odoo.test'},
        ])
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()

        wizard, = captured['wizards']
        self.assertEqual(wizard.summary_message, "3 new databases, 3 updated.")

        new_projects = Project.search([], order='database_version')
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

        # Already-seen database update the project, based on the URL
        # Other dbs should stay untouched
        self.set_returned_databases_list([
            {'name': 'odoo', 'login': 'other_user@odoo.com', 'version': '17.0+e', 'url': 'http://odoo-sa.my.odoo.test'},
        ])
        with self.capture_wizard() as captured:
            Project.action_synchronize_all_databases()
        wizard, = captured['wizards']
        self.assertEqual(wizard.summary_message, "0 new databases, 3 updated.")

        self.assertEqual(Project.search([]), new_projects)
        self.assertRecordValues(new_projects, [
            {
                'name': 'odoo-sa',
                'database_name': 'odoo',
                'database_hosting': 'saas',
                'database_url': 'http://odoo-sa.my.odoo.test',
                'database_api_login': 'other_user@odoo.com',
                'database_version': '17.0',
            },
            {
                'name': 'titi-sarl',
                'database_name': 'titi-sarl',
                'database_hosting': 'saas',
                'database_url': 'http://titi-sarl.my.odoo.test',
                'database_api_login': 'admin@titi-sarl.fr',
                'database_version': '17.0',
            },
            {
                'name': 'toto-nv',
                'database_name': 'toto-nv',
                'database_hosting': 'saas',
                'database_url': 'http://toto-nv.my.odoo.test',
                'database_api_login': 'contact@toto-nv.be',
                'database_version': '18.0',
            },
        ])

    def test_odoocom_db_synchronization(self):
        # First-time-seen database creates a project
        Project = self.env['project.project']
        self.set_returned_databases_list([
            {'name': 'cron-odoo-sa', 'login': 'some_user@odoo.com', 'version': '16.0+e', 'url': 'http://cron-odoo-sa.my.odoo.test'},
        ])
        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases_with_odoocom()
        new_projects = Project.search([])

        self.assertRecordValues(new_projects, [
            {
                'name': 'cron-odoo-sa',
                'database_name': 'cron-odoo-sa',
                'database_hosting': 'saas',
                'database_url': 'http://cron-odoo-sa.my.odoo.test',
                'database_api_login': 'some_user@odoo.com',
                'database_version': '16.0',
                'database_last_synchro': False,
            },
        ])

        cron_odoo_sa_xmlrpc_common = MagicMock()
        cron_odoo_sa_xmlrpc_common.version.return_value = {'server_serie': 'saas~18.4'}
        self.call_resolution_per_uri['http://cron-odoo-sa.my.odoo.test/xmlrpc/2/common'] = cron_odoo_sa_xmlrpc_common
        with freeze_time('2025-01-01 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database should now have been scanned",
        )

        with freeze_time('2025-01-01 23:59'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-01 00:00"),
            "The database shouldn't have been scanned yet",
        )

        with freeze_time('2025-01-02 00:00'):
            Project._cron_synchronize_all_databases()
        self.assertEqual(
            new_projects.database_last_synchro,
            fields.Datetime.from_string("2025-01-02 00:00"),
            "The database should have been scanned",
        )

    @users('db_manager@company.tld')
    def test_user_management(self):
        database = self.env['project.project'].create([{
            'name': 'odoo-sa',
            'database_hosting': 'saas',
            'database_url': 'http://odoo-sa.my.odoo.test',
            'database_name': 'odoo-sa',
            'database_api_login': 'admin',
            'database_api_key': 'admin_apikey',
        }])
        invite_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'invite',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })

        invite_wizard.action_invite_users()
        self.assertCountEqual(self.odoo_sa_xmrpc_common.authenticate.mock_calls, [
            call('odoo-sa', 'admin', 'admin_apikey', {}),
        ])
        self.assertCountEqual(self.odoo_sa_xmrpc_object.execute_kw.mock_calls, [
            call('odoo-sa', -128, 'admin_apikey', 'res.users', 'web_create_users', [], {
                'emails': ['employee@company.tld'],
                'context': {'no_reset_password': True},
            }),
        ])
        self.assertFalse(invite_wizard.error_message)

        self.odoo_sa_xmrpc_common.authenticate.reset_mock()
        self.odoo_sa_xmrpc_object.execute_kw.reset_mock()
        self.odoo_sa_xmrpc_object.execute_kw.side_effect = [[1024], True]
        remove_wizard = self.env['databases.manage_users.wizard'].create({
            'mode': 'remove',
            'database_ids': database.ids,
            'user_ids': self.user_employee.ids,
        })
        invite_wizard.action_remove_users()
        # TODO: self.odoo_sa_xmrpc_common.authenticate.assert_not_called()  # should have recycled the client
        self.assertCountEqual(self.odoo_sa_xmrpc_object.execute_kw.mock_calls, [
            call('odoo-sa', -128, 'admin_apikey', 'res.users', 'search', [
                [('login', 'in', ['employee@company.tld'])],
            ]),
            call('odoo-sa', -128, 'admin_apikey', 'res.users', 'write', [
                [1024],
                {'active': False},
            ]),
        ])

        self.assertFalse(remove_wizard.error_message)
