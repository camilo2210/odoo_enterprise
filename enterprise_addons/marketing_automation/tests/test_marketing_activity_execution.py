from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.tests import tagged, users


@tagged('ma_activity_type')
class TestMarketingActivity(MarketingAutomationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_reference = datetime(2026, 9, 8, 16, 20, 10)

        cls.mailing_lists = cls._create_mailing_list()
        cls.activity_log_note = cls._create_activity_log_note(
            cls.campaign,
            act_values={
                'interval_number': 1,
                'interval_type': 'days',
            },
        )
        cls.activity_subscribe = cls._create_activity_subscribe(
            cls.campaign,
            mailing_list=cls.mailing_lists[0],
            action='add',
            act_values={
                'interval_number': 2,
                'interval_type': 'days',
            },
        )

    def setUp(self):
        super().setUp()
        self._launch_campaign(self.campaign, self.date_reference)

    def test_assert_initial_values(self):
        """ Assert base of tests, notably because visitor is fancy """
        self.assertEqual(
            sorted(self.campaign.participant_ids.mapped('res_id')),
            sorted(self.test_contacts.ids),
            "Should have synchronized setup data"
        )

    @users('user_marketing_automation')
    def test_activity_log_note(self):
        """ Test log_note activity """
        campaign = self.campaign.with_env(self.env)

        # 'begin' scheduled
        self.assertMarketAutoTraces(
            [{
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=1),  # 'begin' delay
                },
                'records': self.test_contacts,
                'status': 'scheduled',
            }],
            self.activity_log_note,
        )

        # launch coupon activity
        with self.mock_datetime_and_now(self.date_reference + relativedelta(days=1, hours=1)), \
             self.mock_mail_gateway():
            campaign._execute_activities()

        self.assertMarketAutoTraces(
            [{
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=1, hours=1),
                },
                'records': self.test_contacts,
                'status': 'processed',
            }],
            self.activity_log_note,
        )

    @users('user_marketing_automation')
    def test_activity_subscribe(self):
        """ Test subscribe_to_list activity """
        campaign = self.campaign.with_env(self.env)

        # 'begin' scheduled
        self.assertMarketAutoTraces(
            [{
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=2),  # 'begin' delay
                },
                'records': self.test_contacts,
                'status': 'scheduled',
            }],
            self.activity_subscribe,
        )

        # launch coupon activity
        with self.mock_datetime_and_now(self.date_reference + relativedelta(days=2, hours=2)), \
             self.mock_mail_gateway():
            campaign._execute_activities()

        self.assertMarketAutoTraces(
            [{
                'fields_values': {
                    'schedule_date': self.date_reference + relativedelta(days=2, hours=2),
                },
                'records': self.test_contacts,
                'status': 'processed',
            }],
            self.activity_subscribe,
        )
