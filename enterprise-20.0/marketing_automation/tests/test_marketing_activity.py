from dateutil.relativedelta import relativedelta

from odoo.fields import Datetime
from odoo.addons.marketing_automation.tests.common import MarketingAutomationCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged, users


class MarketingActivityCommon(MarketingAutomationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_reference = Datetime.from_string('2026-03-04 02:00:00')
        cls.activity = cls._create_activity_mail(
            cls.campaign,
            user=cls.user_marketing_automation,
            act_values={
                'interval_number': 0,
                'interval_type': 'hours',
                'trigger_type': 'begin',
                'view_coordinates': {
                    'activity': {'x': 350, 'y': 0},
                },
            },
        )


@tagged('ma_activity', 'ma_activity_type')
class TestMarketingActivity(MarketingActivityCommon):

    @users('user_marketing_automation')
    def test_activity_type_split(self):
        """ Test split activities. Two kind: either based on interaction (e.g.
        split based on mail_open), either based on a domain. """
        test_records = self.test_contacts
        campaign = self.campaign.with_env(self.env)
        begin_activity = self.activity.with_env(self.env)
        campaign.write({
            'state': 'running',
        })

        with self.mock_datetime_and_now(self.date_reference):
            act_split_domain = self._create_activity_split(
                campaign, [('id', 'in', test_records[:3].ids)],
                act_values={
                    'interval_number': 4,
                    'interval_type': 'hours',
                    'parent_id': begin_activity.id,
                    'trigger_type': 'activity',
                }
            )
            act_split_domain_yes = self._create_activity_mail(
                campaign,
                act_values={
                    'interval_number': 1,
                    'interval_type': 'days',
                    'parent_id': act_split_domain.id,
                    'trigger_type': 'activity',
                },
            )
            act_split_domain_no = self._create_activity_mail(
                campaign,
                act_values={
                    'interval_number': 2,
                    'interval_type': 'days',
                    'is_split_no': True,
                    'parent_id': act_split_domain.id,
                    'trigger_type': 'activity',
                },
            )
            act_split_interaction = self._create_activity_split(
                campaign, [('id', 'in', test_records[:3].ids)],
                act_values={
                    'interval_number': 4,
                    'interval_type': 'hours',
                    'parent_id': begin_activity.id,
                    'trigger_type': 'mail_open',
                }
            )
            act_split_interaction_yes = self._create_activity_mail(
                campaign,
                act_values={
                    'interval_number': 1,
                    'interval_type': 'days',
                    'parent_id': act_split_interaction.id,
                    'trigger_type': 'activity',
                },
            )
            act_split_interaction_no = self._create_activity_mail(
                campaign,
                act_values={
                    'interval_number': 2,
                    'interval_type': 'days',
                    'is_split_no': True,
                    'parent_id': act_split_interaction.id,
                    'trigger_type': 'activity',
                },
            )

        # synchronize participants, launch begin activities
        with self.mock_datetime_and_now(self.date_reference), self.registry_test_mode():
            self.cron_ma_sync_participants.method_direct_trigger()
        with self.mock_datetime_and_now(self.date_reference), self.registry_test_mode():
            self.cron_ma_execute_activities.method_direct_trigger()
        # --> result: interactions are planned (not their children)
        self.assertMarketAutoTraces([{
            'fields_values': {
                'schedule_date': self.date_reference + relativedelta(hours=4),  # interval of activity
            },
            'records': test_records,
            'status': 'scheduled',
        }], act_split_domain)
        self.assertMarketAutoTraces([{
            'fields_values': {
                'schedule_date': self.date_reference + relativedelta(hours=4),  # interval of activity
            },
            'records': test_records,
            'status': 'scheduled',
        }], act_split_interaction)
        self.assertActivityWoTrace(act_split_domain_yes + act_split_domain_no + act_split_interaction_yes + act_split_interaction_no)

        # perform split (automatic, split is done during '_generate_children_traces')
        with self.mock_datetime_and_now(self.date_reference + relativedelta(hours=5)), self.registry_test_mode():
            self.cron_ma_execute_activities.method_direct_trigger()
        self.assertMarketAutoTraces([{
            'records': test_records,
            'status': 'processed',
        }], act_split_domain)
        self.assertMarketAutoTraces([{
            'records': test_records[:3],
            'status': 'scheduled',
        }], act_split_domain_yes)
        self.assertMarketAutoTraces([{
            'records': test_records[3:],
            'status': 'scheduled',
        }], act_split_domain_no)

    @users('user_marketing_automation')
    def test_activity_type_split_interaction(self):
        test_records = self.test_contacts[:2]
        campaign = self.campaign.with_env(self.env)
        campaign.write({'enroll_domain': [('id', 'in', test_records.ids)]})
        with self.mock_datetime_and_now(self.date_reference):
            useless_activity = self._create_activity(campaign, trigger_type='activity', activity_type='mail', parent_id=self.activity.id)
            new_activity_split = self._create_activity(
                campaign, activity_type='split',
                parent_id=useless_activity.id,
                triggering_activity_id=self.activity.id, trigger_type="mail_open")

            new_activity_yes = self._create_activity(campaign, trigger_type="activity", parent_id=new_activity_split.id, activity_type='mail')

            new_activity_no = self._create_activity(campaign, trigger_type="activity", parent_id=new_activity_split.id, is_split_no=True, activity_type='mail')
            self._launch_campaign(campaign)
            campaign.action_synchronize_traces()

        # Send the mailing
        campaign.action_execute_activities()

        with self.mock_datetime_and_now(self.date_reference), self.mock_mail_gateway():
            self.gateway_mail_trace_open(self.activity.mass_mailing_id, test_records[0])

        # Skip the useless activity
        campaign.action_execute_activities()

        self.assertMarketAutoTraces([{
            "records": test_records,
            "status": "scheduled",
            "fields_values": {
                "schedule_date": self.date_reference
            }
        }], new_activity_split)

        campaign.action_execute_activities()
        self.assertMarketAutoTraces([{
            "records": test_records,
            "status": "processed",
        }], new_activity_split)

        self.assertMarketAutoTraces([{
            "records": test_records[0],
            "status": "scheduled"
        }], new_activity_yes)
        self.assertMarketAutoTraces([{
            "records": test_records[1],
            "status": "scheduled"
        }], new_activity_no)

    @users('user_marketing_automation')
    def test_activity_trigger(self):
        test_records = self.test_contacts[:2]
        campaign = self.campaign.with_env(self.env)
        campaign.write({'enroll_domain': [('id', 'in', test_records.ids)]})

        with self.mock_datetime_and_now(self.date_reference):
            new_activity_wait_domain = self._create_activity(campaign, activity_type='structure', trigger_type='wait_value', wait_value_domain=[('email', 'ilike', '%contact.20%')], parent_id=self.activity.id)
            new_activity_interaction_click = self._create_activity(campaign, activity_type='structure', trigger_type='mail_click', parent_id=self.activity.id)
            new_activity_interaction_open = self._create_activity(campaign, activity_type='structure', trigger_type="mail_open", parent_id=new_activity_interaction_click.id, triggering_activity_id=self.activity.id)
            new_activity_log_note = self._create_activity_log_note(campaign, "This shouldn't be used as triggering", {'parent_id': self.activity.id, 'trigger_type': 'activity'})

            with self.assertRaises(ValidationError):
                # Check that we cannot set a non-authorized activity as a triggering one
                new_activity_interaction_click.write({'triggering_activity_id': new_activity_log_note.id})

            self._launch_campaign(campaign)
            with self.mock_mail_gateway(), self.mock_datetime_and_now(self.date_reference):
                campaign.action_execute_activities()

            # need to wait for a value => scheduled
            self.assertMarketAutoTraces([{
                "records": test_records,
                "status": "scheduled",
                "fields_values": {
                    "schedule_date": self.date_reference
                }
            }], new_activity_wait_domain)

            # wait for a processed event => scheduled when event is indeed processed
            self.assertMarketAutoTraces([{
                "records": test_records,
                "status": "scheduled",
                "fields_values": {
                    "schedule_date": False
                }
            }], new_activity_interaction_click)

        test_records[0].write({"email": "ma.test.contact.20@example.com"})
        with self.mock_datetime_and_now(self.date_reference + relativedelta(days=1)):
            # retry the postponed traces by simulating the CRON call
            campaign.action_execute_activities()
            self.gateway_mail_trace_click_simple(self.activity.mass_mailing_id, test_records[0])
        # test_records[0] should be processed now that it has changed to comply with the wait_value_domain
        self.assertMarketAutoTraces([{
            "records": test_records[0],
            "status": "processed",
        }, {
            "records": test_records[1],
            "status": "waiting",  # Still waiting
        }], new_activity_wait_domain)

        # test_records[0] should be processed as the mail was clicked
        self.assertMarketAutoTraces([{
            "records": test_records[0],
            "status": "processed",
        }, {
            "records": test_records[1],
            "status": "scheduled"
        }], new_activity_interaction_click)

        self.assertMarketAutoTraces([{
            "records": test_records[0],
            "status": "scheduled",
        }], new_activity_interaction_open)

        campaign.action_execute_activities()
        self.assertMarketAutoTraces([{
            "records": test_records[0],
            "status": "processed",
        }], new_activity_interaction_open)

    @users('user_marketing_automation')
    def test_activity_trigger_multiple(self):
        """
            Tests that when you have multiple traces on a singular activity that is triggering another one,
            then we set the correct trace as triggering.
            The correct triggering trace should be based on the correct participant_id, as multiple participants
            could have the same res_id on a specific model.
        """
        test_records = self.test_contacts[0]
        campaign = self.campaign.with_env(self.env)

        new_activity_interaction_click = self._create_activity(campaign, activity_type='structure', trigger_type='mail_click', parent_id=self.activity.id)

        # add a test participant
        self.env['marketing.campaign.test'].create([{
            'campaign_id': campaign.id,
            'res_id': test_records.id,
        }]).action_launch_test()

        # execute the trace
        self.activity.trace_ids.filtered_domain([('res_id', '=', test_records.id)]).action_execute()

        # add the dupe test participant
        self.env['marketing.campaign.test'].create([{
            'campaign_id': campaign.id,
            'res_id': test_records.id,
        }]).action_launch_test()
        # execute the duped participant's trace that should not crash
        self.activity.trace_ids.filtered_domain([('res_id', '=', test_records.id), ('state', '=', 'scheduled')]).action_execute()

        test_trace_ids = new_activity_interaction_click.trace_ids
        self.assertEqual(len(test_trace_ids), 2, 'Both test traces should have been generated')
        self.assertEqual(test_trace_ids.mapped('res_id'), [test_records.id, test_records.id], 'Both traces should have the same res_id')
        self.assertNotEqual(test_trace_ids[0].participant_id.id, test_trace_ids[1].participant_id.id, 'Should have different participants')


@tagged('ma_activity')
class TestMarketingActivityBuilder(MarketingActivityCommon):

    @users("user_marketing_automation")
    def test_activity_deletion(self):
        root_activity = self.activity.with_env(self.env)
        activity_to_delete = self._create_activity_mail(
            self.campaign.with_env(self.env), self.env.user,
            act_values={
                "interval_number": 4,
                "parent_id": root_activity.id,
                "trigger_type": "activity",
            },
        )
        activities, grand_children_activities = self.env['marketing.activity'], self.env['marketing.activity']
        for i in range(3):
            activities |= self._create_activity_mail(
                self.campaign.with_env(self.env), self.env.user,
                act_values={
                    "parent_id": root_activity.id,
                    "trigger_type": "activity",
                },
            )
            grand_children_activities |= self._create_activity_mail(
                self.campaign.with_env(self.env), self.env.user,
                act_values={
                    "parent_id": activities[i].id,
                    "trigger_type": "activity",
                },
            )
            grand_children_activities |= self._create_activity_mail(
                self.campaign.with_env(self.env), self.env.user,
                act_values={
                    "parent_id": activities[i].id,
                    "trigger_type": "activity",
                },
            )
        activity_to_delete.action_delete_step('activity')
        self.assertTrue(activity_to_delete.exists())
        activity_to_delete.action_delete_step('delay')
        self.assertFalse(activity_to_delete.exists())

    def test_action_delete_step_cascading_root_activity(self):
        """ Check that deleting the root node also deletes child nodes
            that cannot become root nodes, such as "mail interaction"
            and "wait for value" nodes. """

        #     / mail_open - log_note
        # mail
        #     \ mail_click - wait_for_value - log_note

        campaign = self.campaign.with_env(self.env)
        activity_begin = self.activity.with_env(self.env)

        # First branch:
        activity_1_1_log_note = self._create_activity_log_note(campaign,
            log_note_body='Hi there!',
            act_values={
                'parent_id': activity_begin.id,
                # Add a trigger node on the activity:
                'trigger_type': 'mail_open',
                'triggering_activity_id': activity_begin.id,
                'view_coordinates': {
                    'trigger': {'x': 700, 'y': -100},
                    'activity': {'x': 1050, 'y': -100},
                    'flag': {'x': 1400, 'y': -100}
                },
            })

        # Second branch:
        activity_2_1_mail_click = self._create_activity(campaign,
            activity_type='structure',
            parent_id=activity_begin.id,
            trigger_type='mail_click',
            triggering_activity_id=activity_begin.id,
            view_coordinates={
                'activity': {'x': 700, 'y': 100},
            })
        activity_2_2_wait_value = self._create_activity(campaign,
            activity_type='structure',
            parent_id=activity_2_1_mail_click.id,
            trigger_type='wait_value',
            wait_value_domain='[]',
            view_coordinates={
                'activity': {'x': 1050, 'y': 100},
            })
        activity_2_3_log_note = self._create_activity_log_note(campaign,
            log_note_body='Hello world!',
            act_values={
                'parent_id': activity_2_2_wait_value.id,
                'trigger_type': 'activity',
                'view_coordinates': {
                    'activity': {'x': 1400, 'y': 100},
                    'flag': {'x': 1750, 'y': 100},
                },
            })

        activity_begin.action_delete_step('mail')

        self.assertEqual(len(campaign.marketing_activity_ids), 2)
        self.assertEqual(campaign.marketing_activity_ids[0], activity_1_1_log_note)
        self.assertEqual(campaign.marketing_activity_ids[0].trigger_type, 'begin')
        self.assertEqual(campaign.marketing_activity_ids[0].activity_type, 'log_note')
        self.assertEqual(campaign.marketing_activity_ids[0].log_note_body, 'Hi there!')
        self.assertFalse(campaign.marketing_activity_ids[0].triggering_activity_id)
        self.assertEqual(campaign.marketing_activity_ids[0].view_coordinates, {
            'activity': {'x': 1050, 'y': -100},
            'flag': {'x': 1400, 'y': -100},
        })

        self.assertEqual(campaign.marketing_activity_ids[1], activity_2_3_log_note)
        self.assertEqual(campaign.marketing_activity_ids[1].trigger_type, 'begin')
        self.assertEqual(campaign.marketing_activity_ids[1].activity_type, 'log_note')
        self.assertEqual(campaign.marketing_activity_ids[1].log_note_body, 'Hello world!')
        self.assertFalse(campaign.marketing_activity_ids[1].triggering_activity_id)
        self.assertEqual(campaign.marketing_activity_ids[1].view_coordinates, {
            'activity': {'x': 1400, 'y': 100},
            'flag': {'x': 1750, 'y': 100},
        })


@tagged('ma_activity')
class TestMarketingActivityIntegrity(MarketingActivityCommon):

    @users('user_marketing_automation')
    def test_integrity_view_coordinates(self):
        campaign = self.campaign.with_env(self.env)
        activity = self.activity.with_env(self.env)
        campaign.action_sort_steps()
        # surface incorrect key
        with self.assertRaises(ValidationError):
            activity.write({'view_coordinates': {'bad_key': 'I am the bad guy'}})
        # deep incorrect key
        with self.assertRaises(ValidationError):
            activity.write({'view_coordinates': {'trigger': {'x': {'duh': 'the bad guy'}, 'y': 0}}})
        activity.write({'view_coordinates': {'trigger': {'x': 1, 'y': 2}}})
