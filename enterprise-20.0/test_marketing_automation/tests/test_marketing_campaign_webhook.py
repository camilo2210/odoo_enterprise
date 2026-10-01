from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import common, tagged, users
from odoo.tools import mute_logger

from odoo.addons.test_marketing_automation.tests.common import TestMACommon


@tagged('marketing_automation', 'ma_enroll')
class TestMarketingCampaignWebhook(TestMACommon, common.HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_campaign = cls.env['marketing.campaign'].create({
            'enroll_domain': [],
            'enroll_type': 'webhook',
            'model_id': cls.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'Webhook Test Campaign',
            'user_id': cls.user_marketing_automation.id,
            'webhook_allow_create': True,
            'webhook_log_calls': True,
        })

        cls.activity_begin_mail = cls._create_activity_mail(
            cls.test_campaign,
            user=cls.user_marketing_automation,
            act_values={
                'interval_number': 1,
                'interval_type': 'hours',
                'trigger_type': 'begin',
            },
            mailing_values={
                'body_html': """<div><p>Hello {{ object.name }}</p>
<p>click here <a id="url0" href="https://www.example.com/test/bar?baz=qux">LINK</a></p>
</div>""",
            },
        )
        cls.test_partner_category = cls.env['res.partner.category'].create({
            'name': 'Test Tag',
        })

        # start the campaign to allow participant addition
        cls._launch_campaign(cls, cls.test_campaign)

    @users('admin')
    @mute_logger('odoo.http.server')
    def test_webhook_disabled_or_malformed(self):
        former_webhook_url = self.test_campaign.webhook_url
        self.test_campaign.enroll_type = 'on_demand'
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(former_webhook_url)
        self.assertEqual(response.status_code, 404)

        self.test_campaign.enroll_type = 'webhook'
        self.assertEqual(
            self.test_campaign.webhook_url,
            '%s/mkauto/webhook/%s/%s' % (self.test_campaign.get_base_url(), self.test_campaign.id, self.test_campaign.webhook_uuid),
            'Sanity check: We know the structure of webhook URLs',
        )
        for (message, url) in [
            ('A missing UUID should cause a 404', '%s/mkauto/webhook/%s' % (self.test_campaign.get_base_url(), self.test_campaign.id)),
            ('A missing ID should cause a 404', '%s/mkauto/webhook/65300/%s' % (self.test_campaign.get_base_url(), self.test_campaign.webhook_uuid)),
            ('An UUID belonging to another campaign should cause a 404', '%s/mkauto/webhook/%s/%s' % (self.test_campaign.get_base_url(), self.test_campaign.id, self.campaign.webhook_uuid)),
            ('An invalid UUID should cause a 404', '%s/mkauto/webhook/%s/669933' % (self.test_campaign.get_base_url(), self.test_campaign.id)),
        ]:
            with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
                response = self.url_open(url)
            self.assertEqual(response.status_code, 404, message)

        former_webhook_url = self.test_campaign.webhook_url
        self.test_campaign.action_rotate_webhook_uuid()
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(former_webhook_url)
        self.assertEqual(response.status_code, 404, 'Rotating webhook UUIDs should invalidate former links')

    @users('user_marketing_automation')
    @mute_logger('odoo.models')
    def test_webhook_permissions(self):
        """ Test the permissions of the regular marketing user in regards to webhook behavior """
        # can read webhook fields
        campaign = self.test_campaign.with_user(self.user_marketing_automation)
        campaign_as_admin = self.test_campaign.with_user(self.user_admin)
        self.assertTrue(campaign.webhook_allow_create)
        self.assertTrue(campaign.webhook_url)

        with self.assertRaises(AccessError):
            # Regular users cannot create a webhook-enrolled campaign
            self.env['marketing.campaign'].create({
                'enroll_domain': [],
                'enroll_type': 'webhook',
                'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
                'name': 'Webhook Test Campaign',
            })
        with self.assertRaises(AccessError):
            # Regular users cannot create a webhook-enrolled campaign through the context
            self.env['marketing.campaign'].with_context({'default_enroll_type': 'webhook'}).create({
                'enroll_domain': [],
                'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
                'name': 'Webhook Test Campaign',
            })
        # admin are allowed to
        _new = campaign_as_admin.create({
            'enroll_domain': [],
            'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'Webhook Test Campaign',
        })

        campaign_as_admin.webhook_allow_create = True
        with self.assertRaises(AccessError):
            # Regular users cannot set webhook_allow_create to False
            campaign.webhook_allow_create = False
        campaign_as_admin.webhook_allow_create = False
        with self.assertRaises(AccessError):
            # Regular users cannot set webhook_allow_create to True
            campaign.webhook_allow_create = True

        campaign_as_admin.enroll_type = 'webhook'
        with self.assertRaises(AccessError):
            # Regular users cannot set enrollment type away from Webhook
            campaign.enroll_type = 'on_demand'
        campaign_as_admin.enroll_type = 'on_demand'
        with self.assertRaises(AccessError):
            # Regular users cannot set enrollment type to Webhook
            campaign.enroll_type = 'webhook'
        with self.assertRaises(AccessError):
            # Regular users can't rotate webhook UUIDs
            campaign.action_rotate_webhook_uuid()

    @users('user_marketing_automation')
    @mute_logger('odoo.http.server')
    def test_webhook_requests(self):
        # test that participants can be added through requests
        target_records = self._create_marketauto_records(model='marketing.test.sms')
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url, json={
                'search_domain': [('id', 'in', target_records.ids)],
            })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(target_records - self._get_campaign_participant_records(self.test_campaign),
            'All target records must have been added as participants')

        # added records should be scheduled for the first activity
        self.assertMarketAutoTraces([{
                'records': target_records,
                'status': 'scheduled',
            }],
            self.activity_begin_mail,
        )

        self.env['ir.logging'].sudo().search([('name', '=', 'Webhook Log')]).unlink()
        self.authenticate(None, None)
        # test standalone create_values
        for (message, create_values, expected_response) in [
            ('Webhook should create records from single dicts', {
                'customer_id': self.user_marketing_automation.partner_id.id,
                'description': f'Linked to partner {self.user_marketing_automation.name}',
                'email_from': 'recordToCreate1@example.com',
                'name': 'recordToCreate1',
            }, 200),
            ('Webhook should create multiple records from a list of dicts', [
                {
                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': f'{name}@example.com',
                    'name': name,
                } for name in ['recordToCreateA1', 'recordToCreateA2', 'recordToCreateA3']
            ], 200),
            ('An incorrect value in a dict should prevent record creation', {
                'customer_id': self.user_marketing_automation.partner_id.id,
                'description': f'Linked to partner {self.user_marketing_automation.name}',
                'email_from': 'recordToCreate3@example.com',
                'name': 'recordToCreate3',
                'invalid_field_1212': 'This field does not exist',
            }, 500),
            ('An incorrect value in any value in a list of dict should prevent record creation', [
                {
                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': 'recordToCreateB1@example.com',
                    'name': 'recordToCreateB1',
                },
                {

                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': 'recordToCreateB2@example.com',
                    'name': 'recordToCreateB2',
                },
                {
                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': 'recordToCreate1@example.com',
                    'name': 'recordToCreateB3',
                    'invalid_field_2323': 'This field does not exist',
                },
            ], 500),
        ]:
            with self.subTest(case=message):
                if isinstance(create_values, dict):
                    expected_record_names = [create_values['name']]
                else:
                    expected_record_names = [val['name'] for val in create_values]
                with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
                    response = self.url_open(self.test_campaign.webhook_url, json={
                        'create_values': create_values,
                    })
                self.assertEqual(response.status_code, expected_response)
                # check logs
                ir_logs = self.env['ir.logging'].sudo().search([('name', '=', 'Webhook Log')])
                self.assertEqual(len(ir_logs), 1, 'Only 1 log: either log call, either log error')
                # records
                new_records = self.env['marketing.test.sms'].search([('name', 'in', expected_record_names)])
                if response.status_code == 200:
                    self.assertEqual(len(new_records), len(expected_record_names), message)
                    self.assertFalse(new_records - self._get_campaign_participant_records(self.test_campaign),
                        'All created records should be in the campaign')
                elif response.status_code == 500:
                    self.assertFalse(new_records, message)
                ir_logs.unlink()

        # test if there is both a domain and a create_values
        target_records = self._create_marketauto_records(model='marketing.test.sms')
        new_record_name = 'recordToCreate2'
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url, json={
                'search_domain': [('id', 'in', target_records.ids)],
                'create_values': {
                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': f'{new_record_name}@example.com',
                    'name': new_record_name,
                },
            })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(target_records - self._get_campaign_participant_records(self.test_campaign),
            'All target records must have been added as participants')
        new_record = self.env['marketing.test.sms'].search([('name', '=', new_record_name)])
        self.assertFalse(new_record, 'As the domain resolved to existing records, no new record should be created')

        # test if domain doesn't resolve to anything and there is no create_values
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url, json={
                'search_domain': [('id', '=', 0)],
            })
        self.assertEqual(response.status_code, 200, 'If the domain doesn\'t resolve to existing records and no create_values are provided, the webhook still succeeds')

        # test if there is a create_values but creation is off
        new_record_name = 'recordToCreate3'
        self.test_campaign.webhook_allow_create = False
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url, json={
                'create_values': {
                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': f'{new_record_name}@example.com',
                    'name': new_record_name,
                },
            })
        self.assertEqual(response.status_code, 200, 'If webhooks may not create records and no domain is provided, the webhook should still appear to succeed')
        new_record = self.env['marketing.test.sms'].search([('name', '=', new_record_name)])
        self.assertFalse(new_record, 'The webhook should not create records')

    @mute_logger('odoo.http.server')
    def test_webhook_requests_access(self):
        """ Some low-level checks on security management. Note that partner / user
        privilege escalation is not possible thanks to '_allow_sudo_commands'
        class parameters. """
        self.test_campaign.write({
            'model_id': self.env['ir.model']._get_id('res.partner'),
        })

        # test standalone create_values
        for case, model_name, create_values, expected_response, exp_record_values in [
            (
                'User 2many create', 'res.partner',
                {
                    'email': '"Test" <test@test.example.com>',
                    'name': 'Test',
                    'user_ids': [(0, 0, {'login': 'cacamou'})],
                }, 500, {},
            ),
            (
                'User 2many link', 'res.partner',
                {
                    'email': '"Test" <test@test.example.com>',
                    'name': 'Test',
                    'user_ids': [(4, 1)],
                }, 500, {},
            ),
            # passes, but fields are filtered
            (
                'Protected fields', 'marketing.test.sms',
                {
                    'access_token': '123456',
                    'char_field_with_groups': 'Iamstarlord',
                    'email_from': '"Test" <test.1@test.example.com>',
                    'name': 'Test',
                    'res_partner_category_ids': [Command.link(self.test_partner_category.id), (0, 0, {'name': 'Yolo'})],
                    'user_related_on_customer_id': 1,
                }, 200, {},
            ),
        ]:
            self.test_campaign.write({
                'model_id': self.env['ir.model']._get_id(model_name),
            })
            # for login, pwd in [(None, None), (self.user_marketing_automation.login, self.user_marketing_automation.login)]:
            for login, pwd in [(None, None)]:
                with self.subTest(case=case, login=login):
                    self.authenticate(login, pwd)
                    with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
                        response = self.url_open(self.test_campaign.webhook_url, json={
                            'create_values': create_values,
                        })
                    self.assertEqual(response.status_code, expected_response)
                    # check logs
                    ir_logs = self.env['ir.logging'].search([('name', '=', 'Webhook Log')])
                    self.assertEqual(len(ir_logs), 1, 'Only 1 log: either log call, either log error')
                    # check records
                    name = create_values['name']
                    new_records = self.env[model_name].search([('name', '=', name)])
                    if response.status_code == 500:
                        self.assertFalse(new_records)
                        self.assertIn(f'Campaign Webhook #{self.test_campaign.id} failed', ir_logs.message)
                    else:
                        self.assertEqual(len(new_records), 1)
                        self.assertRecordValues(new_records, [dict(
                            {
                                'access_token': False,
                                'char_field_with_groups': False,
                                'email_from': '"Test" <test.1@test.example.com>',
                                'name': 'Test',
                                'res_partner_category_ids': self.test_partner_category.ids,
                                'user_related_on_customer_id': False,
                            }, **(exp_record_values or {}),
                        )])
                        new_participant = self.env['marketing.participant'].search([
                            ('campaign_id', '=', self.test_campaign.id),
                            ('res_id', '=', new_records.id),
                        ])
                        self.assertEqual(len(new_participant), 1)
                        self.assertIn(f'Webhook #{self.test_campaign.id} triggered with search_domain {{}} and create_values', ir_logs.message)
                        new_participant.unlink()
                        new_records.unlink()
                    ir_logs.unlink()

    @mute_logger('odoo.http.server')
    def test_webhook_requests_protection(self):
        """ Test that malformed input cause no participants to be added """
        self.authenticate(None, None)
        target_records = self._create_marketauto_records(model='marketing.test.sms')
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url, json={
                'search_domain': [
                    ('id', 'in', target_records.ids),
                    ('nonexistant_field', '!=', False),
                ],
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            len(target_records - self._get_campaign_participant_records(self.test_campaign)),
            len(target_records),
            'As there was an error, target records should not get added')

        # test that there needs to be a search_domain or a create_values argument
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url, json={})
        self.assertEqual(response.status_code, 500, 'The webhook should fail if nothing is provided')

    @users('admin')
    @mute_logger('odoo.http.server')
    def test_webhook_test_endpoint(self):
        target_records = self._create_marketauto_records(model='marketing.test.sms')
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url + '/test', json={
                'search_domain': [
                    ('id', 'in', target_records.ids),
                ],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['msg'], 'Webhook test successful. ')
        self.assertEqual(
            len(target_records - self._get_campaign_participant_records(self.test_campaign)),
            len(target_records),
            'In test mode, no record should be added')

        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url + '/test', json={
                'create_values': '{"name": "NameName", "description": self.env.user}',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('msg'),
            'Create argument is malformed: it should either be a dictionary of values, or a list of dictionaries',
            'In test mode, certain errors should be more explicit')

        new_record_name = 'newRecord1'
        with mute_logger('odoo.addons.marketing_automation.models.marketing_campaign'):
            response = self.url_open(self.test_campaign.webhook_url + '/test', json={
                'create_values': {
                    'customer_id': self.user_marketing_automation.partner_id.id,
                    'description': f'Linked to partner {self.user_marketing_automation.name}',
                    'email_from': f'{new_record_name}@example.com',
                    'name': new_record_name,
                },
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('msg').startswith('Webhook test successful.'))
        self.assertEqual(
            len(target_records - self._get_campaign_participant_records(self.test_campaign)),
            len(target_records),
            'In test mode, no records should be created even on a successful call')

    # Helper method to get a campaign's participants' target records
    def _get_campaign_participant_records(self, campaign):
        return sum(campaign.participant_ids.mapped('resource_ref'), start=self.env[campaign.model_name])
