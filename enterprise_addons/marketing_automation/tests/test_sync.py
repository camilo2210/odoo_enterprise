# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.fields import Datetime
from odoo.tests import tagged, users
from odoo.tools import mute_logger


class SyncingCase(MarketingAutomationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_reference = Datetime.from_string('2023-11-08 09:00:00')
        cls.activity_1 = cls._create_activity_mail(
            cls.campaign,
            user=cls.user_marketing_automation,
            act_values={
                'create_date': cls.date_reference - timedelta(days=1),
                'trigger_type': 'begin',
                'interval_number': 1, 'interval_type': 'hours',
            },
        )
        cls.activity_2 = cls._create_activity_mail(
            cls.campaign,
            user=cls.user_marketing_automation,
            act_values={
                'create_date': cls.date_reference - timedelta(days=1),
                'parent_id': cls.activity_1.id,
                'trigger_type': 'activity',
                'interval_number': 1, 'interval_type': 'hours',
            },
        )
        cls.env.flush_all()


@tagged('marketing_automation', 'ma_sync')
class TestDuplicate(SyncingCase):
    """ Test workflow when having duplicate participants or traces. This may
    happen in several occasions, and we should be defensive with duplicates. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.participants = cls.campaign._create_participants(cls.test_contacts[:2].ids)
        cls.participants += cls.campaign._create_participants(cls.test_contacts[:2].ids)
        cls.traces = cls.env['marketing.trace'].create([
            {
                'activity_id': cls.activity_1.id,
                'participant_id': participant.id,
                'state': state,
            }
            for participant, states in zip(
                cls.participants,
                (['scheduled', 'processed'], ['canceled', 'processed'],  # record 0
                 ['scheduled', 'processed'], ['processed', 'processed'],  # record 1
                )
            )
            for state in states
        ])
        cls.mailing_traces = cls.env['mailing.trace'].create([
            {
                'marketing_trace_id': trace.id,
                'model': cls.campaign.model_name,
                'res_id': trace.res_id,
                'sent_datetime': sent_dt,
                'trace_status': trace_status,
                'trace_type': 'mail',
            }
            for trace, (sent_dt, trace_status) in zip(
                cls.traces,
                [
                    # record 0
                    (False, 'outgoing'),
                    (cls.date_reference, 'sent'),
                    (cls.date_reference, 'bounce'),
                    (False, 'error'),
                    # record 1
                    (False, 'outgoing'),
                    (cls.date_reference, 'sent'),
                    (cls.date_reference, 'cancel'),
                    (False, 'error'),
                ]
            )
        ])
        cls.env.flush_all()

    @users('user_marketing_automation')
    def test_statistics(self):
        """ In case of multiple participants / multiple traces per record
        (manual update, unwanted duplication) we may have more traces than
        target records. We consider it is ok, and prefer keeping statistics
        highlighting a potential issue compared to trying to guess a 'mean'
        trace statistics. """
        campaign = self.campaign.with_env(self.env)
        activity_1 = self.activity_1.with_env(self.env)

        # campaign statistics
        self.assertEqual(campaign.running_participant_count, 4)

        # activity statistics
        self.assertEqual(activity_1.processed, 5)
        self.assertEqual(activity_1.rejected, 0)
        self.assertEqual(activity_1.total_bounce, 1)
        self.assertEqual(activity_1.total_click, 0)
        self.assertEqual(activity_1.total_open, 0)
        self.assertEqual(activity_1.total_reply, 0)
        self.assertEqual(activity_1.total_sent, 4)


@tagged('marketing_automation', 'ma_sync', 'ma_tools')
class TestFieldsAndTools(SyncingCase):
    """ Test fields / tools implementation """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.on_demand_campaign = cls.env['marketing.campaign'].create({
            'name': 'On Demand',
            'model_id': cls.env['ir.model']._get_id('res.partner'),
            'enroll_type': 'on_demand',
        })
        cls.activity_begin = cls._create_activity_mail(cls.on_demand_campaign)
        cls.normal_calendar = cls.env['resource.calendar'].create({
            "name": "Normal Calendar",
            "attendance_ids": [(0, 0, {"dayofweek": str(day), "hour_from": 8, "hour_to": 16}) for day in range(5)]
        })
        cls.campaign_w_calendar = cls.env['marketing.campaign'].create({
            'name': "Activities on a calendar",
            'model_id': cls.campaign.model_id.id,
            'scheduling_calendar_id': cls.normal_calendar.id,
        })

        cls.test_partners = cls.env['res.partner'].create([
            {
                'email': f'email{i}@email.com',
                'name': f'Test Partner {i}',
            } for i in range(5)
        ])
        cls.test_contacts = cls.env['mailing.contact'].create([
            {
                'email': partner.email_normalized,
                'partner_id': partner.id,
            }
            for partner in cls.test_partners
        ])

        cls.env.flush_all()

    @users('user_marketing_automation')
    def test_activity_require_sync(self):
        """ Test activity and campaign 'require_sync' field, as well as campaign
        'last_sync_date' behavior """
        campaign = self.campaign.with_env(self.env)
        activity = self.activity_1.with_env(self.env)

        # starting campaign just changes the state, nothing on sync
        campaign.action_start_campaign()
        self.assertFalse(activity.require_sync)
        self.assertFalse(campaign.last_sync_date)
        self.assertFalse(campaign.require_sync)

        # changing time info should update require sync flag
        activity.interval_number = 3
        self.assertTrue(activity.require_sync)
        self.assertFalse(campaign.require_sync, 'Campaign without sync date is never "To Sync"')
        campaign.last_sync_date = self.date_reference - timedelta(days=2)
        self.assertTrue(campaign.require_sync)

        # reset require_sync, update time info again
        activity.require_sync = False
        self.assertFalse(campaign.require_sync)
        activity.interval_type = "weeks"
        self.assertTrue(activity.require_sync)
        self.assertTrue(campaign.require_sync)

        # manually set as synchronized
        with self.mock_datetime_and_now(self.date_reference):
            campaign.action_set_synchronized()
        self.assertFalse(activity.require_sync)
        self.assertEqual(campaign.last_sync_date, self.date_reference)
        self.assertFalse(campaign.require_sync)

    @mute_logger('odoo.addons.mass_mailing.models.mailing', 'odoo.tests')
    def test_activity_schedule_date(self):
        """ Test updating participants in a running campaign, check schedule
        date is set based on trigger type / parent. """
        marketing_campaign = self.env['marketing.campaign'].create({
            'enroll_domain': [('id', 'in', self.test_contacts.ids)],
            'model_id': self.env['ir.model']._get_id(self.test_contacts._name),
            'name': 'My First Campaign',
        })
        parent_activity = self._create_activity_mail(marketing_campaign)
        child_activity = self._create_activity_mail(
            marketing_campaign,
            act_values={
                'parent_id': parent_activity.id,
                'trigger_type': 'mail_not_open',
            },
        )

        self._launch_campaign(marketing_campaign)
        with self.mock_datetime_and_now(self.date_reference):
            [trace.action_execute() for trace in parent_activity.trace_ids]
        self.assertEqual(len(child_activity.trace_ids), len(self.test_contacts))

        child_activity.update({
            'interval_type': 'days',
            'interval_number': 5,
        })
        marketing_campaign._synchronize_traces()

        expected_schedule_date = self.date_reference + timedelta(days=5)
        for trace in child_activity.trace_ids:
            self.assertEqual(trace.schedule_date, expected_schedule_date)

    @users('user_marketing_automation')
    def test_activity_schedule_date_w_calendar(self):
        campaign = self.campaign_w_calendar.with_env(self.env)
        parent_activity = self._create_activity_mail(campaign)
        child_activity = self._create_activity_mail(
            campaign,
            act_values={
                'parent_id': parent_activity.id,
                'trigger_type': 'mail_not_open',
            },
        )
        with self.mock_datetime_and_now(self.date_reference):
            self._launch_campaign(campaign)
            [trace.action_execute() for trace in parent_activity.trace_ids]

        for interval_type, interval_number, planned_time in [
            ["months", 1, 30],
            ["weeks", 1, 7],
            ["weeks", 2, 14],
            ["hours", 3, 3],
            ["days", 5, 5],
        ]:
            with self.subTest(interval_number=interval_number, interval_type=interval_type):
                child_activity.update({
                    'interval_type': interval_type,
                    'interval_number': interval_number,
                })

                if interval_type == "hours":
                    planned_date = self.normal_calendar.plan_hours(planned_time, self.date_reference)
                elif interval_type == "days":
                    planned_date = self.normal_calendar.plan_days(planned_time, self.date_reference)
                else:  # manual check
                    planned_date = self.date_reference + timedelta(days=planned_time)

                campaign.action_synchronize_traces()

                for trace in child_activity.trace_ids:
                    self.assertEqual(trace.schedule_date, planned_date)

    @users('user_marketing_automation')
    def test_campaign_add_participants(self):
        campaign = self.on_demand_campaign.with_env(self.env)

        self._launch_campaign(campaign)
        self.assertFalse(campaign.participant_ids)

        participants = campaign._add_participants_manually(self.test_partners[:2])
        self.assertEqual(len(participants), 2)
        self.assertMarketAutoTraces(
            [{
                'records': self.test_partners[:2],
                'status': 'scheduled',
            }],
            self.activity_begin,
        )

        participants = campaign._add_participants_manually(self.test_partners[:2])
        self.assertEqual(len(participants), 0, "No participants should have been created in this case")
        self.assertMarketAutoTraces(
            [{
                'records': self.test_partners[:2],
                'status': 'scheduled',
            }],
            self.activity_begin,
        )

        campaign.write({
            "enroll_multiple": True,
            "enroll_type": "action",
        })
        participants = campaign._add_participants_manually(self.test_partners[:2])
        self.assertEqual(len(participants), 2, "Participants should be recreated in this case")

    @users('user_marketing_automation')
    def test_campaign_add_participants_from_partners(self):
        campaign = self.on_demand_campaign.with_env(self.env)
        contact_campaign = self.env['marketing.campaign'].create({
            'enroll_type': 'on_demand',
            'model_id': self.env['ir.model']._get_id('mailing.contact'),
            'name': 'On Demand',
        })
        contact_activity_begin = self._create_activity_mail(contact_campaign)
        campaigns = campaign + contact_campaign

        self._launch_campaign(campaign)
        self._launch_campaign(contact_campaign)
        self.assertFalse(campaign.participant_ids)
        self.assertFalse(contact_campaign.participant_ids)

        participants = campaigns._add_participants_manually_from_partners(self.test_partners[:4].ids)
        self.assertEqual(len(participants), 8)
        self.assertMarketAutoTraces(
            [{
                'records': self.test_partners[:4],
                'status': 'scheduled',
            }],
            self.activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts[:4],
                'status': 'scheduled',
            }],
            contact_activity_begin,
        )

        campaigns._remove_participants_manually_from_partners(self.test_partners[:2].ids)
        self.assertMarketAutoTraces(
            [{
                'records': self.test_partners[:2],
                'status': 'canceled',
            }, {
                'records': self.test_partners[2:4],
                'status': 'scheduled',
            }],
            self.activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts[:2],
                'status': 'canceled',
            }, {
                'records': self.test_contacts[2:4],
                'status': 'scheduled',
            }],
            contact_activity_begin,
        )


@tagged('marketing_automation', 'ma_sync')
class TestSyncing(SyncingCase):
    """ Test various cases of synchronization, notably to avoid creating
    duplicate traces. """

    @users('user_marketing_automation')
    def test_assert_initial_values(self):
        """ Test initial values to have a common ground for other tests """
        campaign = self.campaign.with_env(self.env)
        self.assertFalse(campaign.last_sync_date)
        self.assertEqual(campaign.mass_mailing_count, 2)
        self.assertFalse(campaign.require_sync)
        # activities
        for activity in campaign.marketing_activity_ids:
            self.assertEqual(activity.create_date, self.date_reference - timedelta(days=1))
            self.assertFalse(activity.require_sync)
        # participants
        self.assertFalse(campaign.participant_ids)
        self.assertEqual(campaign.running_participant_count, 0)
        self.assertEqual(campaign.completed_participant_count, 0)
        self.assertEqual(campaign.total_participant_count, 0)
        self.assertEqual(campaign.test_participant_count, 0)
        # records
        self.assertEqual(len(self.test_contacts), 10)

    @users('user_marketing_automation')
    def test_campaign_action_synchronize_traces_no_last_sync_date(self):
        """ Test 'action_synchronize_traces' that should not crash when campaign
        has no 'last_sync_date'; should skip actually. """
        campaign = self.campaign.with_env(self.env)
        self.assertFalse(campaign.last_sync_date)

        with self.mock_datetime_and_now(self.date_reference):
            campaign.action_synchronize_traces()
        self.assertEqual(campaign.last_sync_date, self.date_reference)
        self.assertFalse(campaign.participant_ids)
        # should not have any traces
        self.assertActivityWoTrace(self.activity_1 + self.activity_2)

    @users('user_marketing_automation')
    def test_campaign_copy_dupes(self):
        """ Test copy of campaign, should not lead to duplicating traces due
        to bad synchronization propagation. """
        # generate participants
        campaign = self.campaign.with_env(self.env)
        with self.mock_datetime_and_now(self.date_reference):
            campaign._synchronize_participants()
        self.assertEqual(len(campaign.participant_ids), len(self.test_contacts))

        # copy campaign: should not generate duplicates
        with self.mock_datetime_and_now(self.date_reference + timedelta(days=1)):
            new_campaign = campaign.copy()
            new_campaign.action_start_campaign()
        self.assertFalse(new_campaign.last_sync_date, "Copying a campaign should not copy its sync date")
        self.assertEqual(len(new_campaign.marketing_activity_ids), 2)
        new_activity_1 = new_campaign.marketing_activity_ids.filtered(
            lambda a: a.trigger_type == 'begin'
        )
        new_activity_2 = new_campaign.marketing_activity_ids.filtered(
            lambda a: a.trigger_type != 'begin'
        )
        # should not have any traces
        self.assertActivityWoTrace(new_activity_1 + new_activity_2)

        # launch duplicated campaign participants and update: should not generate
        # duplicate traces (notably due to old sync date of campaign)
        with self.mock_datetime_and_now(self.date_reference + timedelta(days=1)):
            new_campaign._synchronize_participants()
            new_campaign._synchronize_traces()

        # should generate traces for 'begin' activity
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
            }],
            new_activity_1,
        )
        # should not generate traces for other activities
        self.assertActivityWoTrace(new_activity_2)

    @users('user_marketing_automation')
    def test_campaign_action_synchronize_participants(self):
        """ Test 'action_synchronize_participants' that should create participants, and create
        traces for beginning activities. """
        # generate participants
        campaign = self.campaign.with_env(self.env)
        campaign.write({'state': 'running'})
        with self.mock_datetime_and_now(self.date_reference):
            campaign.action_synchronize_participants()

        # 'action_synchronize_participants': creates participant / record, with a trace for begin
        # activity only (other traces will be created at process time)
        self.assertEqual(campaign.last_sync_date, self.date_reference)
        self.assertEqual(len(campaign.participant_ids), len(self.test_contacts))
        # should generate traces for 'begin' activity
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
            }],
            self.activity_1,
        )
        # should not generate traces for other activities
        self.assertActivityWoTrace(self.activity_2)

        # create 5 records, remove 5 records, check trace status
        new_contacts = self.env['mailing.contact'].create([
            {
                'country_id': self.env.ref('base.be').id,
                'email': f'new.ma.test.contact.{idx}@example.com',
                'name': f'MATest_{idx}_new',
            }
            for idx in range(5)
        ])
        self.test_contacts[:5].unlink()
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=1)):
            campaign.action_synchronize_participants()
        # create / updated traces
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts[5:],
                'status': 'scheduled',
            }, {
                'records': new_contacts,
                'status': 'scheduled',
            }],
            self.activity_1,
            canceled_res_ids=set(self.test_contacts[:5].ids),
        )
        # should not generate traces for other activities
        self.assertActivityWoTrace(self.activity_2)

    @users('user_marketing_automation')
    def test_campaign_sync_participants_reject_unlink(self):
        """ Test state of traces when having participants being out of the
        campaign due to enroll_domain or record being removed. """
        campaign = self.campaign.with_env(self.env)
        with self.mock_datetime_and_now(self.date_reference):
            campaign._synchronize_participants()
        self.assertEqual(len(campaign.participant_ids), 10, 'All records synced')

        deleted_contact = self.test_contacts[0]
        self.test_contacts[0].unlink()

        excluded_contact = self.test_contacts[1]
        excluded_contact.name = 'OutOfFilter'

        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=2)):
            campaign._synchronize_participants()
            # set participant as complete -> cancels traces also
            test_participant = campaign.participant_ids.filtered(lambda p: p.res_id == self.test_contacts[2].id)
            test_participant.action_set_completed_manual()

        running_records = self.test_contacts - deleted_contact - excluded_contact - self.test_contacts[2]
        self.assertMarketAutoTraces(
            [{
                'participants': campaign.participant_ids.filtered(lambda p: p.res_id in running_records.ids),
                'participants_state': 'running',
                'records': running_records,
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),  # already synchronized before at date + 1 hour
                },
                'status': 'scheduled',
            }, {
                'participants': campaign.participant_ids.filtered(lambda p: p.res_id in self.test_contacts[2].ids),
                'participants_state': 'completed',
                'records': self.test_contacts[2],
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=2),  # set at cancel time
                    'state_msg': 'Marked as completed',
                },
                'status': 'canceled',
            }, {
                'participants': campaign.participant_ids.filtered(lambda p: p.res_id in excluded_contact.ids),
                'participants_state': 'rejected',
                'records': excluded_contact,
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=2),  # set at cancel time
                    'state_msg': 'Record no longer matches campaign filter',
                },
                'status': 'canceled',
            }, {
                'participants': campaign.participant_ids.filtered(lambda p: p.res_id in deleted_contact.ids),
                'participants_state': 'unlinked',
                'records': deleted_contact,
                'records_missing': True,
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=2),  # set at cancel time
                    'state_msg': 'Record deleted',
                },
                'status': 'canceled',
            }],
            self.activity_1,
        )

    @users('user_marketing_automation')
    def test_participants_creation_dupes(self):
        """ This test may fail randomly based on time if not launched with
        fix in 'action_synchronize_traces' : comparing activity.create_date
        with campaign.last_sync_date may fail as the first one comes from
        sql NOW, second one from datetime.now . We don't want duplicates
        marketing traces hence having to be tolerant on date check. """
        campaign = self.env['marketing.campaign'].create({
            'enroll_domain': [('id', '=', self.test_contacts[0].id)],
            'model_id': self.env['ir.model']._get_id(self.test_contacts._name),
            'marketing_activity_ids': [
                (0, 0, {
                    'activity_type': 'mail',
                    'name': 'Test Activity',
                    'trigger_type': 'begin',
                }),
            ],
            'name': 'Test Participant Dupes',
        })
        campaign._synchronize_participants()

        # execute immediately (same second as the creation)
        # because of that condition (precision is second)
        # >>> a.create_date >= campaign.last_sync_date
        campaign.action_synchronize_traces()

        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts[0],
                'status': 'scheduled',
            }],
            campaign.marketing_activity_ids,
        )

    @users('user_marketing_automation')
    def test_participants_creation_then_update_dupes(self):
        """ Test participants creation then update when adding new activities
        on a running campaign. We should not duplicate traces, notably when
        a participant had traces on a new activity that is then updated
        automatically. """
        campaign = self.campaign.with_env(self.env)
        old_activity_begin = self.activity_1.with_env(self.env)

        # init participants and traces
        with self.mock_datetime_and_now(self.date_reference):
            campaign.action_start_campaign()
            campaign._synchronize_participants()
            campaign._synchronize_traces()

        # should be initialized with test data
        self.assertEqual(len(campaign.participant_ids), len(self.test_contacts))
        # should generate traces for 'begin' activity
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
            }],
            old_activity_begin,
        )
        # should not generate traces for other activities
        self.assertActivityWoTrace(self.activity_2)

        # add a new begin activity, and a child to activity_1
        new_activity_begin = self._create_activity_mail(
            campaign,
            user=self.user_admin,
            act_values={
                'create_date': self.date_reference + timedelta(hours=1),
                'trigger_type': 'begin',
                'interval_number': 1, 'interval_type': 'hours',
            },
        )
        new_activity_mail_open = self._create_activity_mail(
            campaign,
            user=self.env.user,
            act_values={
                'create_date': self.date_reference + timedelta(hours=1),
                'parent_id': old_activity_begin.id,
                'trigger_type': 'mail_open',
                'interval_number': 0,
            },
        )
        for activity in new_activity_begin + new_activity_mail_open:
            self.assertEqual(activity.create_date, self.date_reference + timedelta(hours=1))
            self.assertTrue(activity.require_sync)
        self.assertEqual(campaign.last_sync_date, self.date_reference)
        self.assertTrue(campaign.require_sync, 'Campaign should require a sync due to new activity')

        # add new participants
        new_records = self.env['mailing.contact'].create([
            {
                'email': 'ma.test.new.1@example.com',
                'name': 'MATest_new_1',
            }, {
                'email': 'ma.test.new.2@example.com',
                'name': 'MATest_new_2',
            }
        ])
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=2)):
            campaign._synchronize_participants()

        # should have generated one trace / begin activity for the new participant
        self.assertEqual(len(campaign.participant_ids), len(self.test_contacts) + len(new_records))
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts + new_records,
                'status': 'scheduled',
            }],
            old_activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': new_records,
                'status': 'scheduled',
            }],
            new_activity_begin,
        )
        self.assertActivityWoTrace(new_activity_mail_open)

        # run begin activities, should schedule children
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=3)), self.mock_mail_gateway():
            campaign._execute_activities()
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts + new_records,
                'status': 'processed',
                'trace_status': 'sent',
            }],
            old_activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': new_records,
                'status': 'processed',
                'mail_values': {
                    'email_from': self.user_admin.email_formatted,
                },
                'trace_status': 'sent',
            }],
            new_activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
                'fields_values': {
                    'schedule_date': False,
                },
            }, {
                'records': new_records,
                'status': 'scheduled',
                'fields_values': {
                    'schedule_date': False,
                },
            }],
            new_activity_mail_open,
        )

        # triggers mail_open activity, to check brother / opposite trace update
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)), \
             self.mock_mail_gateway():
            self.gateway_mail_trace_open(old_activity_begin.mass_mailing_id, new_records[0])
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
                'fields_values': {
                    'schedule_date': False,
                },
            }, {
                'records': new_records[0],
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=4),  # updated at event time
                },
                'trace_status': 'sent',
            }, {
                'records': new_records[1],
                'status': 'scheduled',
                'fields_values': {
                    'schedule_date': False,
                },
            }],
            new_activity_mail_open,
        )

        # now add a brother activity for mail_not_open, to check brother "not creation" when not necessary
        new_activity_mail_click = self._create_activity_mail(
            campaign,
            user=self.env.user,
            act_values={
                'create_date': self.date_reference + timedelta(hours=1),
                'parent_id': old_activity_begin.id,
                'trigger_type': 'mail_click',
                'interval_number': 0,
            },
        )
        new_activity_mail_not_open = self._create_activity_mail(
            campaign,
            user=self.env.user,
            act_values={
                'create_date': self.date_reference + timedelta(hours=1),
                'parent_id': old_activity_begin.id,
                'trigger_type': 'mail_not_open',
                'interval_number': 2, 'interval_type': 'days',
            },
        )

        # campaign should require an update, update it
        self.assertTrue(campaign.require_sync, 'Campaign should require an update')
        with self.mock_datetime_and_now(self.date_reference + timedelta(days=3)):
            campaign._synchronize_traces()
        # should have synchronized traces for all participants / all begin activities
        # without dupes for the new_record (already had one, don't create again)
        self.assertMarketAutoTraces(
            [{
                'check_mail': False,  # mails removed from mock
                'records': self.test_contacts + new_records[1],
                'status': 'processed',
                'trace_status': 'sent',
            }, {
                'check_mail': False,  # mails removed from mock
                'records': new_records[0],
                'status': 'processed',
                'trace_status': 'open',
            }],
            old_activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
            }, {
                'check_mail': False,  # mails removed from mock
                'records': new_records,
                'status': 'processed',
                'mail_values': {
                    'email_from': self.user_admin.email_formatted,
                },
                'trace_status': 'sent',
            }],
            new_activity_begin,
        )
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts + new_records,
                'status': 'scheduled',
                'fields_values': {
                    # user-action based activities should not have a schedule date, which should be
                    # computed based on delay once user has done the action e.g. 2 days after
                    # having opened the mail
                    'schedule_date': False,
                },
            }],
            new_activity_mail_click,
        )
        # new_records[0] has no trace, because in '_synchronize_traces' we don't generate
        # traces if an "opposite positive brother" has been processed (aka: do not generate
        # mail_not_open if mail_open for the same parent was already managed)
        # TDE FIXME: for complete stats, should generate a canceled trace, like done in 'process_event'
        self.assertMarketAutoTraces(
            [{
                'records': self.test_contacts,
                'status': 'scheduled',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(days=2, hours=3),  # begin delay + activity trigger delay
                },
            }, {
                'records': new_records[1],
                'status': 'scheduled',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(days=2, hours=3),  # execute delay (new participant) + activity trigger delay
                },
            }],
            new_activity_mail_not_open,
        )
