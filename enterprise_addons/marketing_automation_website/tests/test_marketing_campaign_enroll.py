from odoo.addons.marketing_automation.tests.test_marketing_campaign_enroll import MarketingCampaignEnrollCommon
from odoo.addons.website.tests.test_website_visitor import WebsiteVisitorTestsCommon
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged, users
from odoo.tools import SQL


@tagged("marketing_automation", "ma_enroll", "ma_enroll_action")
class TestMarketingCampaignAction(MarketingCampaignEnrollCommon, WebsiteVisitorTestsCommon, common.HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        model_record = cls.env['ir.model'].sudo().search([('model', '=', 'res.partner')])
        model_record.write({'website_form_access': True})
        fields_records = cls.env['ir.model.fields'].sudo().search([('model_id', '=', model_record.id), ('name', 'in', ('name', 'email'))])
        cls.env.cr.execute(
            SQL('UPDATE ir_model_fields SET website_form_blacklisted=false WHERE id in %s', tuple(fields_records.ids))
        )

        cls.campaign.write({
            'enroll_type': 'action',
            'model_id': cls.env['ir.model']._get_id('res.partner'),
            'state': 'running',
            'title': 'Action Enroll Campaign',
        })

        cls.test_contacts = cls.env['res.partner'].create([
            {
                'email': f'test.contact.{idx}@ma.example.com',
                'name': f'MATest Contact {idx}',
            }
            for idx in range(5)
        ])

    def setUp(self):
        super().setUp()

        self.test_visitors = self.env['website.visitor'].create([
            {'access_token': self.test_contacts[0].id},
            {'access_token': self.test_contacts[1].id},
        ])

        self.test_tracks = self.env['website.track'].create([
            {'visitor_id': self.test_visitors[0].id, 'page_id': self.tracked_page.id, 'url': self.tracked_page.url},
            {'visitor_id': self.test_visitors[0].id, 'page_id': self.tracked_page.id, 'url': self.tracked_page.url},
            {'visitor_id': self.test_visitors[1].id, 'page_id': self.tracked_page.id, 'url': self.tracked_page.url},
            {'visitor_id': self.test_visitors[0].id, 'page_id': self.tracked_page_2.id, 'url': self.tracked_page_2.url},
            {'visitor_id': self.test_visitors[1].id, 'url': '/untracked-url'},
        ])

    def test_assert_initial_values(self):
        """ Assert base of tests, notably because visitor is fancy """
        self.assertEqual(self.test_visitors.partner_id, self.test_contacts[:2])

    @users('user_marketing_automation')
    def test_action_check_fields(self):
        """ Check fields validity """
        campaign = self.campaign.with_env(self.env)

        # limited to res.partner for the time being
        with self.assertRaises(ValidationError):
            campaign.write({'model_id': self.env['ir.model']._get_id('mailing.contact')})

    @users('user_marketing_automation')
    def test_action_form_submit(self):
        """ Check enroll on website forms """
        campaign = self.campaign.with_env(self.env)
        campaign.write({'enroll_action_type': 'form_submit'})
        self.assertFalse(campaign.participant_ids)

        self.authenticate(None, None)
        form_data = {
            'csrf_token': self.csrf_token(),
            'email': 'bastien.poiluche@example.com',
            'name': "Bastien Poiluche",
        }

        _response = self.url_open(
            '/website/form/res.partner',
            data=form_data,
        )
        self.assertEqual(len(campaign.participant_ids), 1, "Should have a new participant")
        partner = self.env['res.partner'].search([('id', '=', campaign.participant_ids.res_id)])
        self.assertEqual(partner.name, "Bastien Poiluche")
        self.assertEqual(partner.email, 'bastien.poiluche@example.com')

    @users('user_marketing_automation')
    def test_action_page_visit(self):
        """ Check enrolling on page_visit, based on visitors and tracked pages """
        campaign = self.campaign.with_env(self.env)
        pages = (self.tracked_page + self.tracked_page_2).with_env(self.env)
        pages.mapped('name')  # should have read access
        expected_partners = self.test_contacts[:2]

        campaign.sudo().write({  # TDE fixme: access fail on page access -> to check
            'enroll_action_type': 'page_visit',
            'website_page_ids': [(6, 0, pages.ids)],
        })

        date_test = self.date_reference
        with self.mock_datetime_and_now(date_test), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as _captured_triggers_sync:
            new = campaign._synchronize_participants()

        # partners enrolled
        self.assertEqual(sorted(new.mapped('res_id')), sorted(expected_partners.ids))
