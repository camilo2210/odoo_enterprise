# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.test_marketing_automation.tests.common import TestMACommon
from odoo.tests import tagged, users
from odoo.exceptions import AccessError
from odoo.tools import mute_logger


@tagged('marketing_automation')
class TestDataCampaign(TestMACommon):

    @users('user_marketing_automation')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_get_campaign_from_template(self):
        double_opt_in_campaign_vals = self.env['marketing.campaign'].get_action_marketing_campaign_from_template('double_opt_in')
        welcome_campaign_vals = self.env['marketing.campaign'].get_action_marketing_campaign_from_template('welcome')
        hot_contacts_campaign_vals = self.env['marketing.campaign'].get_action_marketing_campaign_from_template('hot_contacts')

        # test that campaigns get created when user_marketing_automation
        self.assertTrue(bool(double_opt_in_campaign_vals['res_id']))
        self.assertTrue(bool(welcome_campaign_vals['res_id']))
        self.assertTrue(bool(hot_contacts_campaign_vals['res_id']))

        # test that the campaign_id is correctly set for each of created mailings
        double_opt_in_campaign = self.env['marketing.campaign'].browse(double_opt_in_campaign_vals['res_id'])
        welcome_campaign = self.env['marketing.campaign'].browse(welcome_campaign_vals['res_id'])
        hot_contacts_campaign = self.env['marketing.campaign'].browse(hot_contacts_campaign_vals['res_id'])
        self.assertEqual(double_opt_in_campaign.marketing_activity_ids.mass_mailing_id.campaign_id, double_opt_in_campaign.utm_campaign_id)
        self.assertEqual(welcome_campaign.marketing_activity_ids.mass_mailing_id.campaign_id, welcome_campaign.utm_campaign_id)
        self.assertEqual(hot_contacts_campaign.marketing_activity_ids.mass_mailing_id.campaign_id, hot_contacts_campaign.utm_campaign_id)

        # test that the child activities of a campaign get created
        campaign_action = self.env['marketing.campaign'].get_action_marketing_campaign_from_template('commercial_prospection')
        self.assertTrue(bool(campaign_action['res_id']))
        campaign = self.env['marketing.campaign'].browse(campaign_action['res_id'])
        self.assertTrue(len(campaign.marketing_activity_ids) == 3)
        # test that activities have their own children objects (depending on their activity type)
        for activity in campaign.marketing_activity_ids:
            if activity.activity_type == 'mail':
                self.assertTrue(bool(activity.mass_mailing_id))
            elif activity.activity_type == 'action':
                self.assertTrue(bool(activity.server_action_id))

    @users('employee')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_get_campaign_from_template_as_employee(self):
        with self.assertRaises(AccessError):
            self.env['marketing.campaign'].get_action_marketing_campaign_from_template('commercial_prospection')
