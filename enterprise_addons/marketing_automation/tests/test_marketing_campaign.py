from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Datetime
from odoo.tests import Form, tagged, users


@tagged("marketing_automation", "utm")
class TestMarketingCampaign(MarketingAutomationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_reference = Datetime.from_string('2026-02-26 09:00:00')
        cls.activity = cls._create_activity_mail(
            cls.campaign,
            user=cls.user_marketing_automation,
            act_values={
                'trigger_type': 'begin',
                'interval_number': 0, 'interval_type': 'hours',
            },
        )
        cls._create_mailing_list()

    @users('user_marketing_automation')
    def test_action_retry_failed_blocked_for_marketing_automation(self):
        """ Ensure retrying a mailing linked to a marketing campaign is blocked. """
        mailing = self.activity.mass_mailing_id

        self.assertTrue(mailing.use_in_marketing_automation)

        # Verify that calling action_retry_failed raises a UserError
        with self.assertRaises(UserError, msg="Retrying a marketing automation mailing should be blocked."):
            mailing.action_retry_failed()

    @users('user_marketing_automation')
    def test_create_records_with_xml_ids(self):
        # The function tests creation of records.
        # If record is deleted and then re-created it has to get same xmlid.
        email = 'ma.test.new.1@example.com'
        name = 'MATest_new_1'
        create_xmls = {
                'xml_id': 'marketing_automation.mail_contact_temp',
                'values': {
                    'email': email,
                    'name': name,
                }
            }
        self.env['marketing.campaign'].sudo()._create_records_with_xml_ids({'mailing.contact': [create_xmls]})

        # Retrieve the records using the XML IDs and verify they exist
        record = self.env.ref('marketing_automation.mail_contact_temp', raise_if_not_found=False)
        self.assertTrue(record, "Record should exist after creation.")
        self.assertEqual(record.name, name, f"The value should be {name}")
        self.assertEqual(record.email, email, f"The value should be {email}")

        # Now delete the record
        record.unlink()
        self.assertFalse(record.exists(), "Record should be deleted.")
        record = self.env.ref('marketing_automation.mail_contact_temp', raise_if_not_found=False)
        self.assertFalse(record, "The record with XML ID 'marketing_automation.mail_contact_temp' should not exist.")

        # Now re-create record and check values again
        self.env['marketing.campaign'].sudo()._create_records_with_xml_ids({'mailing.contact': [create_xmls]})
        record = self.env.ref('marketing_automation.mail_contact_temp', raise_if_not_found=False)
        self.assertTrue(record, "Record should exist after being re-created.")
        self.assertEqual(record.name, name, f"The value should be {name}")
        self.assertEqual(record.email, email, f"The value should be {email}")

    @users('user_marketing_automation')
    def test_duplicate_campaign(self):
        """ Test duplicating a campaign: should not duplicate traces
        and consider mailings as already sent through duplicates """
        original_campaign = self.campaign.with_user(self.env.user)

        # Add server activity to campaign
        server_action = self.env['ir.actions.server'].sudo().create({
            'name': 'Test Server Action',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'code',
            'code': 'pass',
        })
        self._create_activity(self.campaign, mailing=None, action=server_action)

        duplicated_campaign = original_campaign.copy()
        for campaign in original_campaign + duplicated_campaign:
            campaign._synchronize_participants()
            with self.mock_mail_gateway(mail_unlink_sent=False):
                campaign._execute_activities()
            for activity in campaign.marketing_activity_ids:
                with self.subTest(msg=f'campaign.name="{campaign.name}"', activity=activity):
                    self.assertMarketAutoTraces(
                        [{
                            'status': 'processed',
                            'records': self.test_contacts,
                            'trace_status': 'sent',
                        }], activity)

    @users('user_marketing_automation')
    def test_model_update(self):
        """Test that updating the target model resets all model-dependent fields."""
        partner_model = self.env['ir.model']._get('res.partner')
        partner_field_name = self.env['ir.model.fields']._get('res.partner', 'name')
        partner_field_write_date = self.env['ir.model.fields']._get('res.partner', 'write_date')
        user_model = self.env['ir.model']._get('res.users')
        user_field_name = self.env['ir.model.fields']._get('res.users', 'name')

        partner_filter, user_filter = self.env["mailing.filter"].create([
            {
                "name": "Test Filter (Partner)",
                "mailing_model_id": partner_model.id,
                "mailing_domain": repr([("active", "=", True)]),
            }, {
            "name": "Test Filter (User)",
            "mailing_model_id": user_model.id,
            "mailing_domain": repr(['&', ("active", "=", True), ("partner_id.active", "=", True)]),
            }
        ])

        campaign_form = Form(self.env["marketing.campaign"], view="marketing_automation.marketing_campaign_view_form_trigger")
        campaign_form.title = 'My Test Campaign'
        self.assertEqual(campaign_form.model_id, partner_model)

        campaign_form.mailing_filter_ids.add(partner_filter)
        campaign_form.enroll_unique_field_id = partner_field_name
        self.assertEqual(campaign_form.enroll_domain, repr([("active", "=", True)]))
        self.assertTrue(campaign_form.enroll_recipients_count > 0, 'Should have at least default admin partner in recipients')
        self.assertEqual(campaign_form.model_id, partner_model)

        # invalid enroll_unique_field_id
        campaign_form.enroll_unique_field_id = partner_field_write_date
        with self.assertRaises(ValidationError):
            campaign_form.save()
        campaign_form.enroll_unique_field_id = user_field_name
        with self.assertRaises(ValidationError):
            campaign_form.save()
        campaign_form.enroll_unique_field_id = partner_field_name

        # update model
        campaign_form.model_id = user_model
        self.assertFalse(campaign_form.enroll_unique_field_id, 'Changing model should reset unicity field')
        self.assertEqual(campaign_form.enroll_domain, repr([]), 'Changing model should reset domain')
        self.assertFalse(campaign_form.mailing_filter_ids, 'Changing model should reset mailing filters')
        campaign_form.enroll_unique_field_id = user_field_name
        campaign_form.mailing_filter_ids.add(user_filter)
        self.assertEqual(campaign_form.enroll_domain, repr(['&', ("active", "=", True), ("partner_id.active", "=", True)]))
        self.assertTrue(campaign_form.enroll_recipients_count > 0, 'Should have at least default admin user in recipients')
        campaign_form.save()

        # reset model
        campaign_form.model_id = self.env["ir.model"]
        self.assertEqual(campaign_form.enroll_domain, repr([]))
        self.assertFalse(campaign_form.enroll_unique_field_id)
        self.assertEqual(campaign_form.enroll_recipients_count, 0)
        self.assertFalse(campaign_form.mailing_filter_ids)


@tagged('marketing_automation')
class TestMarketingCampaignIntegrity(MarketingAutomationCommon):

    @users('user_marketing_automation')
    def test_writing_error_coordinates(self):
        campaign = self.campaign.with_env(self.env)
        campaign.action_sort_steps()
        # surface incorrect key
        with self.assertRaises(ValidationError):
            campaign.write({'view_coordinates': {'bad_key': 'I am the bad guy'}})
        # deep incorrect key
        with self.assertRaises(ValidationError):
            campaign.write({'view_coordinates': {'trigger': {'x': {'duh': 'the bad guy'}, 'y': 0}}})
        campaign.write({'view_coordinates': {'trigger': {'x': 1, 'y': 2}}})
