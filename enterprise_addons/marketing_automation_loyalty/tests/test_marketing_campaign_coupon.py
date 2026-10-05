from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.marketing_automation.tests.test_marketing_campaign_enroll import MarketingCampaignEnrollCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged, users


@tagged("marketing_automation", "ma_activity_type")
class TestMarketingCampaignAction(MarketingCampaignEnrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_reference = datetime(2026, 9, 8, 9, 25, 10)
        cls.loyalty_template_activity = cls.env.ref("loyalty.mail_template_loyalty_card")
        cls.loyalty_template_activity.write({'subject': 'Ease Finding Me {{ object.partner_id.name }}'})

        cls.test_loyalty_program_promo, cls.test_loyalty_program_gift = cls.env['loyalty.program'].create([
            {
                'applies_on': 'current',
                'mail_template_id': cls.env.ref("loyalty.mail_template_gift_card").id,
                'name': 'Promo Code',
                'program_type': 'promo_code',
                'portal_point_name': 'Discount Point(s)',
                'portal_visible': False,
                'trigger': 'with_code',
            }, {
                'applies_on': 'future',
                'mail_template_id': cls.env.ref("loyalty.mail_template_gift_card").id,
                'name': 'Gift Cards',
                'program_type': 'gift_card',
                'portal_point_name': '$',
                'portal_visible': True,
                'trigger': 'auto',
            }
        ])

        with cls.mock_datetime_and_now(cls.date_reference):
            cls.campaign = cls.env['marketing.campaign'].create({
                'enroll_type': 'on_demand',
                'model_id': cls.env['ir.model']._get_id('mailing.contact'),
                'state': 'running',
                'title': 'Coupon Campaign',
                'user_id': cls.user_marketing_automation.id,
            })
            cls.activity_coupon = cls._create_activity(
                cls.campaign,
                activity_type='coupon',
                create_date=cls.date_reference,
                interval_number=1,
                interval_type='days',
                loyalty_mail_template_id=cls.loyalty_template_activity.id,
                loyalty_program_id=cls.test_loyalty_program_promo.id,
                trigger_type='begin',
            )

        cls.test_contacts = cls.env['res.partner'].create([
            {
                'email': f'test.contact.{idx}@ma.example.com',
                'name': f'MATest Contact {idx}',
            }
            for idx in range(5)
        ])
        cls.test_mailing_contacts = cls.env['mailing.contact'].create([
            {
                'email': partner.email_formatted,
                'partner_id': partner.id,
                'name': partner.name
            }
            for partner in cls.test_contacts
        ] + [
            {
                'email': 'no.partner.0@ma.example.com',
                'name': 'MATest NoPartner 0',
            }
        ])
        cls.failing_contacts = cls.test_mailing_contacts[-1]

    def setUp(self):
        super().setUp()
        self._launch_campaign(self.campaign, date_reference=self.date_reference)
        with self.mock_datetime_and_now(self.date_reference):
            self.campaign._add_participants_manually(
                self.test_mailing_contacts,
            )

    def test_assert_initial_values(self):
        """ Assert base of tests, notably because visitor is fancy """
        self.assertEqual(
            sorted(self.campaign.participant_ids.mapped('res_id')),
            sorted(self.test_mailing_contacts.ids),
            "on_demand should have only contacts added through '_add_participants_manually'"
        )

    @users('user_marketing_automation')
    def test_loyalty_fields(self):
        """ Assert constraints and field coherency """
        activity_coupon = self.activity_coupon.with_env(self.env)

        # computed fields
        self.assertEqual(activity_coupon.name, 'Send Coupon: Promo Code')
        self.assertEqual(activity_coupon.description, '<p>Promo Code</p>')

        # required loyalty program
        with self.assertRaises(ValidationError):
            activity_coupon.write({'loyalty_program_id': False})
        # unaccepted program_type
        with self.assertRaises(ValidationError):
            activity_coupon.write({'loyalty_program_id': self.test_loyalty_program_gift.id})

        # reset
        activity_coupon.write({'activity_type': 'log_note', 'log_note_body': 'Zboing'})
        self.assertFalse(activity_coupon.loyalty_mail_template_id)
        self.assertFalse(activity_coupon.loyalty_program_id)

    def test_loyalty_flow(self):
        """ Test 'coupon' activity_type """
        campaign = self.campaign.with_env(self.env)

        # coupon 'begin' scheduled
        self.assertMarketAutoTraces(
            [{
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=1),  # 'begin' delay
                },
                'records': self.test_mailing_contacts,
                'status': 'scheduled',
            }],
            self.activity_coupon,
        )

        # launch coupon activity
        with self.mock_datetime_and_now(self.date_reference + relativedelta(days=1, hours=1)), \
             self.mock_mail_gateway():
            campaign._execute_activities()
        # MA result: traces updated (failed = no customer)
        self.assertMarketAutoTraces(
            [{
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=1, hours=1),  # execution time (?)
                },
                'records': self.test_mailing_contacts - self.failing_contacts,
                'status': 'processed',
            }, {
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=1, hours=1),  # execution time (?)
                    'state_msg': 'Coupon could not be sent to the customer',
                },
                'records': self.failing_contacts,
                'status': 'error',
            }],
            self.activity_coupon,
        )
        # Other result: custom mail template sent
        new_mails = self._new_mails
        self.assertEqual(len(new_mails), len(self.test_mailing_contacts - self.failing_contacts))
        self.assertEqual(
            sorted([m['subject'] for m in new_mails]),
            sorted([f'Ease Finding Me {rec.name}' for rec in self.test_mailing_contacts - self.failing_contacts])
        )
