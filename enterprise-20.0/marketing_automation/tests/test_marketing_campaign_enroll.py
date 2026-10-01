from contextlib import nullcontext
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged, users
from odoo.tools import mute_logger


class MarketingCampaignEnrollCommon(MarketingAutomationCommon, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.campaign.write({
            'state': 'running',
        })
        cls.activity_begin_mail = cls._create_activity_mail(
            cls.campaign,
            user=cls.user_marketing_automation,
            act_values={
                'trigger_type': 'begin',
                'interval_number': 0, 'interval_type': 'hours',
            },
        )

        # Juanuary 02 to ease cross-months / cross-year checks // 2029 as 2028 is a leap year
        cls.date_reference = datetime(2029, 1, 2, 10, 15, 30)


@tagged("marketing_automation", "ma_enroll", "ma_enroll_action")
class TestMarketingCampaignAction(MarketingCampaignEnrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mailing_lists = cls._create_mailing_list()

    @users('user_marketing_automation')
    def test_campaign_reset_values(self):
        campaign = self.campaign.with_user(self.env.user)
        campaign.write({
            "enroll_action_type": "subscribe",
            "enroll_type": "action",
            "mailing_list_ids": [(6, 0, self.mailing_lists[:2].ids)],
            "model_id": self.env['ir.model']._get_id('res.partner'),
        })
        campaign.flush_recordset()
        self.assertEqual(campaign.mailing_list_ids, self.mailing_lists[:2])

        campaign.write({"enroll_type": "domain"})
        campaign.flush_recordset()
        self.assertFalse(campaign.enroll_action_type, "Action type should be reset")
        self.assertFalse(campaign.mailing_list_ids, "Linked mailing lists should be reset")


@tagged("marketing_automation", "ma_enroll", "ma_enroll_date")
class TestMarketingCampaignAnniversary(MarketingCampaignEnrollCommon):
    """ Test anniversary-based enroll mode for campaigns. Based on a date(time)
    field, participants are enrolled once at least a year passed since their
    anniversary. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.campaign.write({
            'enroll_date_delay_number': 1,
            'enroll_date_delay_order': 'after',
            'enroll_date_delay_type': 'days',
            'enroll_date_field_id': cls.env['ir.model.fields']._get('mailing.contact', 'last_clicked_datetime').id,
            'enroll_type': 'anniversary',
            'state': 'running',
        })

        # Juanuary 02 to ease cross-months / cross-year checks // 2029 as 2028 is a leap year
        cls.date_past_light1 = datetime(2029, 1, 1, 9, 13, 28)  # -1 day
        cls.date_past_light2 = datetime(2028, 12, 30, 8, 10, 25)  # -3 day
        cls.date_past = datetime(2028, 2, 29, 7, 7, 22)  # incidentaly, "one day" before date_future_leap
        cls.date_past_year = datetime(2027, 12, 31, 5, 5, 20)  # -2 day, -1 year
        cls.date_future_light1 = datetime(2029, 1, 3, 11, 17, 33)  # +1 day
        cls.date_future_leap = datetime(2029, 3, 2, 12, 20, 35)  # +2 months
        cls.date_future_year = datetime(2030, 1, 1, 13, 23, 38)  # -1 day, +1 year

        count = 5
        (
            cls.records_today,
            cls.records_past_light1, cls.records_past_light2, cls.records_past, cls.records_past_year,
            cls.records_future_light1, cls.records_future_leap, cls.records_future_year,
        ) = [
            cls.env['mailing.contact'].create([
                {
                    'country_id': cls.test_countries[idx % len(cls.test_countries)].id,
                    'email': f'ma.test.contact.{idx}.{dt}@example.com',
                    'last_clicked_datetime': dt,
                    'last_replied_datetime': False,
                    'name': f'MATest_{idx}_{dt}',
                }
                for idx in range(count)
            ])
            for dt in (
                cls.date_reference,
                cls.date_past_light1, cls.date_past_light2, cls.date_past, cls.date_past_year,
                cls.date_future_light1, cls.date_future_leap, cls.date_future_year,
            )
        ]
        cls.test_contacts += (
            cls.records_today +
            cls.records_past_light1 + cls.records_past_light2 + cls.records_past + cls.records_past_year +
            cls.records_future_light1 + cls.records_future_leap + cls.records_future_year
        )

    def test_assert_initial_values(self):
        """ Just ensure inherited / created test data validity """
        self.assertEqual(len(self.test_contacts), 50)
        self.assertEqual(len(self.test_contacts.filtered('last_clicked_datetime')), 40)

    @users('user_marketing_automation')
    def test_anniversary_check_fields(self):
        """ Check fields validity """
        campaign = self.campaign.with_user(self.env.user)
        test_field = self.env['ir.model.fields']._get('mailing.contact', 'last_clicked_datetime')
        test_field_partner = self.env['ir.model.fields']._get('res.partner', 'create_date')
        test_field_user_notstored = self.env['ir.model.fields']._get('res.users', 'offline_since')
        self.assertEqual(campaign.enroll_date_field_id, test_field)

        # model update -> invalid combination
        with self.assertRaises(ValidationError):
            campaign.write({'model_id': self.env['ir.model']._get_id('res.partner')})
        # field should be set
        with self.assertRaises(ValidationError):
            campaign.write({'enroll_date_field_id': False})
        # non stored field
        with self.assertRaises(ValidationError):
            campaign.write({
                'enroll_date_field_id': test_field_user_notstored.id,
                'model_id': self.env['ir.model']._get_id('res.users'),
            })
        # invalid model field
        with self.assertRaises(ValidationError):
            campaign.write({'enroll_date_field_id': test_field_partner.id})
        # not a date(time) field
        with self.assertRaises(ValidationError):
            campaign.write({'enroll_date_field_id': self.env['ir.model.fields']._get('mailing.contact', 'name').id})

        # invalid delay
        with self.assertRaises(ValidationError):
            campaign.write({'enroll_date_delay_number': -1})

        # reset (update me if necessary)
        reset_values = {
            'enroll_date_delay_number': 1,
            'enroll_date_delay_order': 'after',
            'enroll_date_delay_type': 'days',
            'enroll_date_field_id': test_field.id,
            'enroll_type': 'anniversary',
        }
        for update in ({'enroll_type': 'domain'}, {'enroll_type': 'on_demand'}):
            campaign.write(reset_values)
            self.assertEqual(campaign.enroll_date_field_id, test_field)
            campaign.write(update)
            for fname in [
                'enroll_date_field_id', 'enroll_date_delay_number', 'enroll_date_delay_order', 'enroll_date_delay_type',
            ]:
                self.assertFalse(campaign[fname], 'Date-based fields should have been reset')

    @users('user_marketing_automation')
    def test_anniversary_synchronize_participants_quick(self):
        """ Ensure base of anniversary-based campaigns: day-based check, no re
        enrolling unless +1 year. Actual year should not really impact (aka
        future date, right day = enrolled) """
        campaign = self.campaign.with_user(self.env.user)

        # test date: March 2, beware delay of 1 day
        date_test = self.date_reference.replace(year=self.date_future_leap.year, month=self.date_future_leap.month, day=self.date_future_leap.day)
        # expected: March 1 -> also works for Feb 29 in non leap years
        expected1 = self.records_past
        # expected: date_future_leap: in the future, but year does not matter
        expected2 = self.records_future_leap

        # datetime: whatever the year, it is set to "current cron running time"
        expected1_dt = [
            record.last_clicked_datetime.replace(
                year=2029, month=3, day=1,  # current year, 29/2 -> 1/3
                hour=10, minute=15, second=30)  # forced to cron running time
            for record in expected1
        ]
        expected2_dt = [
            record.last_clicked_datetime.replace(
                year=2029,  # current year
                hour=10, minute=15, second=30)  # forced to cron running time
            for record in expected2
        ]

        # check delay is taken into account -> test on record date field value, should not sync
        with self.mock_datetime_and_now(date_test), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as captured_triggers_sync:
            new = campaign._synchronize_participants()
        self.assertEqual(sorted(new.mapped('res_id')), sorted(expected1.ids))
        self.assertEqual(sorted(new.mapped('anniversary_dt')), sorted(expected1_dt))
        self.assertEqual(len(captured_triggers_sync.records), 0, 'Done, nothing rescheduled')

        # anniversary + campaign delay
        with self.mock_datetime_and_now(date_test + relativedelta(days=1)), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as captured_triggers_sync:
            new = campaign._synchronize_participants()
        self.assertEqual(sorted(new.mapped('res_id')), sorted(expected2.ids))
        self.assertEqual(sorted(new.mapped('anniversary_dt')), sorted(expected2_dt))
        self.assertEqual(len(captured_triggers_sync.records), 0, 'Done, nothing rescheduled')

        # relaunch sync -> already enrolled contacts should not be enrolled again
        with self.mock_datetime_and_now(date_test + relativedelta(hours=1)):
            new = campaign._synchronize_participants()
        self.assertFalse(new)

        expected2_dt_2 = [
            record.last_clicked_datetime.replace(
                year=2030,  # new current year
                hour=10, minute=15, second=30)  # forced to cron running time
            for record in expected2
        ]

        # one year later -> should be enroller again
        with self.mock_datetime_and_now(date_test + relativedelta(years=1, days=1)), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as captured_triggers_sync:
            new = campaign._synchronize_participants()
        self.assertEqual(sorted(new.mapped('res_id')), sorted(expected2.ids))
        self.assertEqual(sorted(new.mapped('anniversary_dt')), sorted(expected2_dt_2))
        self.assertEqual(len(captured_triggers_sync.records), 0, 'Done, nothing rescheduled')

    @users('user_marketing_automation')
    def test_date_check_fields(self):
        """ Ensure base of date-based campaigns: actual date based check. """
        campaign = self.campaign.with_user(self.env.user)
        campaign.write({'enroll_type': 'date'})
        # should not reset when going from anniversary to date
        self.assertEqual(campaign.enroll_date_delay_number, 1)
        self.assertEqual(campaign.enroll_date_delay_order, 'after')
        self.assertEqual(campaign.enroll_date_delay_type, 'days')

    @users('user_marketing_automation')
    def test_date_synchronize_participants_quick(self):
        """ Ensure base of date-based campaigns: actual date based check. """
        campaign = self.campaign.with_user(self.env.user)
        campaign.write({'enroll_type': 'date'})

        # test date: March 2, beware delay of 1 day
        date_test = self.date_reference.replace(year=self.date_future_leap.year, month=self.date_future_leap.month, day=self.date_future_leap.day)

        # check delay is taken into account -> test on record date field value, should not sync
        with self.mock_datetime_and_now(date_test), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as captured_triggers_sync:
            new = campaign._synchronize_participants()
        self.assertFalse(new)
        self.assertEqual(len(captured_triggers_sync.records), 0, 'Done, nothing rescheduled')

        # date + campaign delay
        expected = self.records_future_leap
        with self.mock_datetime_and_now(date_test + relativedelta(days=1)), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as captured_triggers_sync:
            new = campaign._synchronize_participants()
        self.assertEqual(sorted(new.mapped('res_id')), sorted(expected.ids))
        self.assertEqual(len(captured_triggers_sync.records), 0, 'Done, nothing rescheduled')

        # relaunch sync -> already enrolled contacts should not be enrolled again
        with self.mock_datetime_and_now(date_test + relativedelta(hours=1)):
            new = campaign._synchronize_participants()
        self.assertFalse(new)

        # one year later -> should not be enrolled, wrong year
        with self.mock_datetime_and_now(date_test + relativedelta(years=1, days=1)), \
             self.capture_triggers('marketing_automation.ir_cron_campaign_sync_participants') as captured_triggers_sync:
            new = campaign._synchronize_participants()
        self.assertFalse(new)


@tagged("marketing_automation", "ma_enroll")
class TestMarketingCampaignDomain(MarketingCampaignEnrollCommon):
    """ Test enroll_domain-based enroll mode for campaigns. It enrolls participants
    based on an input filtering domain. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # add some more contacts for batch check
        cls.test_contacts += cls.env['mailing.contact'].create([
            {
                'country_id': cls.test_countries[idx % len(cls.test_countries)].id,
                'email': f'ma.test.contact.add.{idx}@example.com',
                'name': f'MATest_{idx + 10}',
            }
            for idx in range(30)
        ])

    def test_assert_initial_values(self):
        """ Just ensure inherited / created test data validity """
        self.assertEqual(len(self.test_contacts), 40)
        self.assertEqual(len(set(self.test_contacts.mapped('name'))), 40, 'Name is unique on all contacts')
        self.assertEqual(len(set(self.test_contacts.mapped('country_id'))), 4, 'Country is not unique')

    @users('user_marketing_automation')
    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_domain_enroll_unique_field(self):
        test_contacts = self.test_contacts.with_user(self.env.user)
        # make email of first 10 repeated on 20+ and 30+ (aka: 2 duplicates / record for 10 first)
        # and void one value, to check support of Falsy values
        # for country, see in common.py: rotate on 1 Falsy + 4 countries
        for idx in range(10):
            test_contacts[20 + idx].write({'email': test_contacts[idx].email})
            test_contacts[30 + idx].write({'email': test_contacts[idx].email})
        (test_contacts[0] + test_contacts[20] + test_contacts[30]).write({'email': False})

        email_field = self.env['ir.model.fields']._get('mailing.contact', 'email')
        country_field = self.env['ir.model.fields']._get('mailing.contact', 'country_id')
        last_clicked_datetime_field = self.env['ir.model.fields']._get('mailing.contact', 'last_clicked_datetime')

        campaign = self.campaign.with_user(self.env.user)
        # note sorting of contact is name asc, id desc -> should be respected when searching for new participants
        for unique_field, should_raise, out_of_unique_vals, exp_records in [
            # char field: void value is kept
            (email_field, False, {'email': 'unique@example.com'}, test_contacts[:20]),
            # m2o field: void value is rejected (FIXME probably)
            (country_field, False, {'country_id': self.env.ref('base.ca').id}, test_contacts[1:5]),
            # datetime field: not supported
            (last_clicked_datetime_field, True, {}, test_contacts),
        ]:
            with self.subTest(fname=unique_field.name, ftype=unique_field.ttype):
                campaign.participant_ids.unlink()
                self.assertEqual(campaign.running_participant_count, 0)
                raiseIfInvalidField = self.assertRaises(ValidationError) if should_raise else nullcontext()
                with raiseIfInvalidField:
                    campaign.write({
                        'enroll_unique_field_id': unique_field.id,
                    })
                if should_raise:  # reset to default if testing invalid input
                    campaign.write({'enroll_unique_field_id': False})

                with self.mock_datetime_and_now(self.date_reference):
                    self._launch_campaign(campaign)
                self.assertEqual(campaign.running_participant_count, len(exp_records))
                self.assertEqual(sorted(campaign.participant_ids.mapped('res_id')), sorted(exp_records.ids))

                if should_raise:
                    continue

                # made unique again -> should be added in campaign
                test_contacts[-1].write(out_of_unique_vals)
                campaign._synchronize_participants()
                new_exp_records = exp_records + test_contacts[-1]
                self.assertEqual(campaign.running_participant_count, len(new_exp_records))
                self.assertEqual(sorted(campaign.participant_ids.mapped('res_id')), sorted(new_exp_records.ids))
