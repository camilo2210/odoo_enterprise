from datetime import timedelta

from odoo.addons.test_mail.data.test_mail_data import MAIL_TEMPLATE
from odoo.addons.test_marketing_automation.tests.common import TestMACommon
from odoo.exceptions import ValidationError
from odoo.fields import Datetime
from odoo.tests import tagged, users
from odoo.tools import mute_logger


class ActivityTriggersCase(TestMACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date_reference = Datetime.from_string('2023-11-08 09:00:00')

        # --------------------------------------------------
        # TEST RECORDS, using marketing.test.sms (customers)
        #
        # 2 times
        # - 3 records with partners
        # - 1 records wo partner, but email/mobile
        # - 1 record wo partner/email/mobile
        # --------------------------------------------------
        cls.test_records_base = cls._create_marketauto_records(model='marketing.test.sms', count=2)
        cls.test_records = cls.test_records_base
        cls.test_customers = cls.test_records.customer_id
        cls.test_records_ko = cls.test_records_base[4] + cls.test_records_base[9]
        cls.test_records_ok = cls.test_records - cls.test_records_ko

        cls.campaign = cls.env['marketing.campaign'].create({
            'enroll_domain': [('id', 'in', cls.test_records.ids)],
            'model_id': cls.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'Test Campaign',
        })

        cls.test_mailing_mail = cls._create_mailing(
            'marketing.test.sms',
            email_from=cls.user_marketing_automation.email_formatted,
            keep_archives=True,
            mailing_type='mail',
            user_id=cls.user_marketing_automation.id,
        )
        cls.test_mailing_sms = cls._create_mailing(
            'marketing.test.sms',
            mailing_type='sms',
            user_id=cls.user_marketing_automation.id,
            sms_force_send=True,
        )
        cls.test_wa_template = cls._create_wa_template(
            'marketing.test.sms',
        )

        cls.test_sa_descr = cls.env['ir.actions.server'].create([
            {
                'code': f"""
for record in records:
    record.write({{'description': (record.description or '') + ' - {description}'}})""",
                'model_id': cls.env['ir.model']._get_id('marketing.test.sms'),
                'name': f'Update {description}',
                'state': 'code',
            } for description in [
                # mail
                'mail_open', 'mail_not_open',
                'mail_reply', 'mail_not_reply',
                'mail_click', 'mail_not_click',
                'mail_bounce',
                # sms
                'sms_click', 'sms_not_click',
                'sms_bounce',
                # whatsapp
                'whatsapp_click', 'whatsapp_not_click',
                'whatsapp_open', 'whatsapp_not_open',
                'whatsapp_reply', 'whatsapp_not_reply',
                'whatsapp_bounce',
                # other
                'action',
            ]
        ])
        (
            # mail
            cls.test_sa_descr_mail_open, cls.test_sa_descr_mail_not_open,
            cls.test_sa_descr_mail_reply, cls.test_sa_descr_mail_not_reply,
            cls.test_sa_descr_mail_click, cls.test_sa_descr_mail_not_click,
            cls.test_sa_descr_mail_bounce,
            # sms
            cls.test_sa_descr_sms_click, cls.test_sa_descr_sms_not_click,
            cls.test_sa_descr_sms_bounce,
            # whatsapp
            cls.test_sa_descr_wa_click, cls.test_sa_descr_wa_not_click,
            cls.test_sa_descr_wa_open, cls.test_sa_descr_wa_not_open,
            cls.test_sa_descr_wa_reply, cls.test_sa_descr_wa_not_reply,
            cls.test_sa_descr_wa_bounce,
            # other
            cls.test_sa_descr_action,
        ) = cls.test_sa_descr
        cls.test_sa_unlink = cls.env['ir.actions.server'].create({
            'code': "records.unlink()",
            'model_id': cls.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'Unlink',
            'state': 'code',
        })

        cls.env.flush_all()


@tagged('marketing_automation', 'ma_sync')
class TestActivityTriggers(ActivityTriggersCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # begin activities: MAIL, SMS and WHATSAPP
        cls.activity_begin_mail = cls._create_activity(
            cls.campaign,
            create_date=cls.date_reference,
            mailing=cls.test_mailing_mail,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )
        cls.activity_begin_sms = cls._create_activity(
            cls.campaign,
            create_date=cls.date_reference,
            mailing=cls.test_mailing_sms,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )
        cls.activity_begin_wa = cls._create_activity(
            cls.campaign,
            create_date=cls.date_reference,
            wa_template=cls.test_wa_template,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )
        cls.activity_begin_sa = cls._create_activity(
            cls.campaign,
            create_date=cls.date_reference,
            action=cls.test_sa_descr_action,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )

        (
            # sub activities mail triggers
            cls.activity_sa_mail_not_open,
            cls.activity_sa_mail_open,
            cls.activity_sa_mail_not_reply,
            cls.activity_sa_mail_reply,
            cls.activity_sa_mail_not_click,
            cls.activity_sa_mail_click,
            cls.activity_sa_mail_bounce,
            # sub activities for sms triggers
            cls.activity_sa_sms_not_click,
            cls.activity_sa_sms_click,
            cls.activity_sa_sms_bounce,
            # sub activities for whatsapp triggers
            cls.activity_sa_wa_not_read,
            cls.activity_sa_wa_read,
            cls.activity_sa_wa_not_reply,
            cls.activity_sa_wa_reply,
            cls.activity_sa_wa_not_click,
            cls.activity_sa_wa_click,
            cls.activity_sa_wa_bounce,
        ) = (
            cls._create_activity(
                cls.campaign,
                action=server_action,
                parent_id=parent.id,
                interval_number=itv,
                interval_type='days',
                trigger_type=trigger_type,
            )
            for trigger_type, server_action, parent, itv in (
                # mail
                ("mail_not_open", cls.test_sa_descr_mail_not_open, cls.activity_begin_mail, 5),
                ("mail_open", cls.test_sa_descr_mail_open, cls.activity_begin_mail, 1),
                ("mail_not_reply", cls.test_sa_descr_mail_not_reply, cls.activity_begin_mail, 5),
                ("mail_reply", cls.test_sa_descr_mail_reply, cls.activity_begin_mail, 1),
                ("mail_not_click", cls.test_sa_descr_mail_not_click, cls.activity_begin_mail, 5),
                ("mail_click", cls.test_sa_descr_mail_click, cls.activity_begin_mail, 1),
                ("mail_bounce", cls.test_sa_descr_mail_bounce, cls.activity_begin_mail, 1),
                # sms
                ("sms_not_click", cls.test_sa_descr_sms_not_click, cls.activity_begin_sms, 5),
                ("sms_click", cls.test_sa_descr_sms_click, cls.activity_begin_sms, 1),
                ("sms_bounce", cls.test_sa_descr_sms_bounce, cls.activity_begin_sms, 1),
                # whatsapp
                ("whatsapp_not_open", cls.test_sa_descr_wa_not_open, cls.activity_begin_wa, 5),
                ("whatsapp_open", cls.test_sa_descr_wa_open, cls.activity_begin_wa, 1),
                ("whatsapp_not_reply", cls.test_sa_descr_wa_not_reply, cls.activity_begin_wa, 5),
                ("whatsapp_reply", cls.test_sa_descr_wa_reply, cls.activity_begin_wa, 1),
                ("whatsapp_not_click", cls.test_sa_descr_wa_not_click, cls.activity_begin_wa, 5),
                ("whatsapp_click", cls.test_sa_descr_wa_click, cls.activity_begin_wa, 1),
                ("whatsapp_bounce", cls.test_sa_descr_wa_bounce, cls.activity_begin_wa, 1),
            )
        )
        # sub activities other
        cls.activity_mail_activity = cls._create_activity(
                cls.campaign,
                action=cls.test_sa_descr_action,
                parent_id=cls.activity_begin_mail.id,
                interval_number=2,
                interval_type='hours',
                trigger_type='activity',
        )
        cls.activity_sms_activity = cls._create_activity(
                cls.campaign,
                action=cls.test_sa_descr_action,
                parent_id=cls.activity_begin_sms.id,
                interval_number=2,
                interval_type='hours',
                trigger_type='activity',
        )
        cls.activity_wa_activity = cls._create_activity(
                cls.campaign,
                action=cls.test_sa_descr_action,
                parent_id=cls.activity_begin_wa.id,
                interval_number=2,
                interval_type='hours',
                trigger_type='activity',
        )

        # other branches (currently breaks tests)
        # cls.activity_collect_reply_mail = cls._create_activity_mail(
        #     cls.campaign,
        #     act_values={
        #         'interval_number': 10,
        #         'interval_type': 'days',
        #         'name': 'Mail Activity Collect',
        #         'parent_id': False,
        #         'trigger_type': 'collect_reply',
        #     },
        # )

        cls.env.flush_all()

    def test_assert_initial_values(self):
        """ Check initial state, notably partners """
        self.assertEqual(len(self.test_records), 10)
        self.assertEqual(len(self.test_customers), 6)

        self._launch_campaign(self.campaign, date_reference=self.date_reference)
        for activity in (
            self.activity_begin_mail + self.activity_begin_sms +
            self.activity_begin_wa + self.activity_begin_sa
        ):
            self.assertMarketAutoTraces(
                [{
                    'records': self.test_records,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': self.date_reference + timedelta(hours=1),
                    },
                }],
                activity,
            )

    @mute_logger('odoo.addons.mail.models.mail_mail', 'odoo.addons.mail.models.mail_thread')
    @users('user_marketing_automation')
    def test_reaction_triggers(self):
        """ Test triggers (open / not_open, read / not read, ...) for mail, sms
        and whatsapp. """
        campaign = self.campaign.with_env(self.env)
        test_records = self.test_records.with_env(self.env)
        test_records_ok = self.test_records_ok.with_env(self.env)
        test_records_ko = self.test_records_ko.with_env(self.env)

        self._launch_campaign(campaign, date_reference=self.date_reference)
        self.assertActivityWoTrace(
            self.activity_sa_mail_open + self.activity_sa_mail_not_open +
            self.activity_sa_mail_reply + self.activity_sa_mail_not_reply +
            self.activity_sa_mail_click + self.activity_sa_mail_not_click +
            self.activity_sa_mail_bounce +
            self.activity_sa_sms_not_click + self.activity_sa_sms_click +
            self.activity_sa_sms_bounce +
            self.activity_sa_wa_not_read + self.activity_sa_wa_read +
            self.activity_sa_wa_not_reply + self.activity_sa_wa_reply +
            self.activity_sa_wa_not_click + self.activity_sa_wa_click +
            self.activity_sa_wa_bounce +
            self.activity_mail_activity + self.activity_sms_activity + self.activity_wa_activity
        )

        # First traces are processed, email, SMSes and WA msgs are sent (or failed)
        date_send = self.date_reference + timedelta(hours=1)  # ok for send mailing
        date_opened = date_send + timedelta(hours=2)  # simulating opened
        date_not_action = date_send + timedelta(days=5)  # 5 days delay before triggering 'did not reply' or similar
        with self.mock_datetime_and_now(date_send), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mockSMSGateway():
            campaign._execute_activities()

        self.assertMarketAutoTraces(
            [{
                'records': test_records_ok,
                'records_to_partner': {r.id: r.customer_id for r in test_records_ok},
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                },
                'trace_status': 'sent',
            }, {
                'records': test_records_ko,
                'status': 'canceled',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'Email cancelled',
                },
                'trace_failure_type': 'mail_email_missing',
                'trace_status': 'cancel',
            }],
            self.activity_begin_mail,
        )
        self.assertMarketAutoTraces(
            [{
                'records': test_records_ok,
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                },
                'trace_status': 'pending',  # forced send -> waiting provider update
            }] + [{
                'records': record,
                'status': 'canceled',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'SMS cancelled',
                },
                'trace_content': f"Test SMS for {record.name} click on",
                'trace_failure_type': 'sms_number_missing',
                'trace_status': 'cancel',
            } for record in test_records_ko],
            self.activity_begin_sms,
        )
        self.assertMarketAutoTraces(
            [{
                'records': test_records_ok,
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                },
                'trace_content': "<p>Hello your much wow template value</p>",
                'trace_status': 'sent',
            }] + [{
                'records': record,
                'status': 'error',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'WhatsApp failed',
                },
                'trace_content': "<p>Hello your much wow template value</p>",
                'trace_failure_type': 'phone_invalid',
                'trace_status': 'error',
            } for record in test_records_ko],
            self.activity_begin_wa,
        )
        self.assertMarketAutoTraces(
            [{
                'records': test_records,
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                },
            }],
            self.activity_begin_sa,
        )
        # collect_reply: unscheduled (waiting for replies)
        # self.assertActivityWoTrace(self.activity_collect_reply_mail)

        for sub_activity, schedule_date in [
            # mail
            (self.activity_sa_mail_open, False),  # mail open: no date, as user input
            (self.activity_sa_mail_not_open, date_not_action),
            (self.activity_sa_mail_reply, False),  # mail reply: no date, as user input
            (self.activity_sa_mail_not_reply, date_not_action),
            (self.activity_sa_mail_click, False),  # mail click: no date, as user input
            (self.activity_sa_mail_not_click, date_not_action),
            (self.activity_sa_mail_bounce, False),  # mail bounce: no date, as user input
            # sms
            (self.activity_sa_sms_click, False),  # sms click: no date, as user input
            (self.activity_sa_sms_not_click, date_not_action),
            (self.activity_sa_sms_bounce, False),  # sms bounce: no date, as user input
            # whatsapp
            (self.activity_sa_wa_read, False),  # wa read: no date, as user input
            (self.activity_sa_wa_not_read, date_not_action),
            (self.activity_sa_wa_reply, False),  # wa replied: no date, as user input
            (self.activity_sa_wa_not_reply, date_not_action),
            (self.activity_sa_wa_click, False),  # wa click: no date, as user input
            (self.activity_sa_wa_not_click, date_not_action),
            (self.activity_sa_wa_bounce, False),  # wa bounce: no date, as user input
            # other
            (self.activity_mail_activity, date_send + timedelta(hours=2)),
            (self.activity_sms_activity, date_send + timedelta(hours=2)),
            (self.activity_wa_activity, date_send + timedelta(hours=2)),
        ]:
            self.assertMarketAutoTraces(
                [{
                    'records': test_records,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': schedule_date,
                    },
                }],
                sub_activity,
            )

        # Simulate open / reply / click
        # - active traces should be processed, schedule date updated
        # - opposite traces should be canceled
        for action, action_sa, opposite_sa in (
            # mail
            ("mail_open", self.activity_sa_mail_open, self.activity_sa_mail_not_open),
            ("mail_reply", self.activity_sa_mail_reply, self.activity_sa_mail_not_reply),
            ("mail_click", self.activity_sa_mail_click, self.activity_sa_mail_not_click),
            # sms
            ("sms_click", self.activity_sa_sms_click, self.activity_sa_sms_not_click),
            # whatsapp
            ("whatsapp_open", self.activity_sa_wa_read, self.activity_sa_wa_not_read),
            ("whatsapp_reply", self.activity_sa_wa_reply, self.activity_sa_wa_not_reply),
            ("whatsapp_click", self.activity_sa_wa_click, self.activity_sa_wa_not_click),
        ):
            todo = test_records_ok[:5]
            with self.mock_datetime_and_now(date_opened):
                for record in todo:
                    if action == "mail_open":
                        self.gateway_mail_trace_open(self.activity_begin_mail.mass_mailing_id, record)
                        state_msg = 'Parent activity mail opened'
                    elif action == "mail_reply":
                        self.gateway_mail_trace_reply(MAIL_TEMPLATE, self.activity_begin_mail.mass_mailing_id, record)
                        state_msg = 'Parent activity mail replied'
                    elif action == "mail_click":
                        self.gateway_mail_trace_click(self.activity_begin_mail.mass_mailing_id, record, "LINK")
                        state_msg = 'Parent activity mail clicked'
                    elif action == "sms_click":
                        self.gateway_sms_click(self.activity_begin_sms.mass_mailing_id, record, use_sent_sms=False, sms_status='pending')
                        state_msg = 'Parent activity SMS clicked'
                    elif action == "whatsapp_open":
                        self.whatsapp_msg_read_with_records(record)
                        state_msg = 'Parent whatsapp message opened'
                    elif action == "whatsapp_reply":
                        self.whatsapp_answer_with_records(record, mock=False)
                        state_msg = 'Parent whatsapp message replied to'
                    elif action == "whatsapp_click":
                        self.whatsapp_msg_click_with_records(record, button_index=0)
                        state_msg = 'Parent whatsapp message clicked'
            # sub action scheduled
            self.assertMarketAutoTraces(
                [{
                    'records': todo,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': date_opened + timedelta(days=1),
                        'state_msg': False,
                    },
                }, {
                    'records': test_records - todo,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': False,
                    },
                }],
                action_sa,
            )
            # opposition action is canceled
            self.assertMarketAutoTraces(
                [{
                    'records': todo,
                    'status': 'canceled',
                    'fields_values': {
                        'schedule_date': date_opened,
                        'state_msg': state_msg,
                    },
                }, {
                    'records': test_records - todo,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': date_not_action,
                    },
                }],
                opposite_sa,
            )

    @mute_logger('odoo.addons.mail.models.mail_mail')
    @users('user_marketing_automation')
    def test_reaction_triggers_bounce_fail(self):
        """ Test specific 'bounce' and 'failed' triggers, that should
        cancel a lot of things as if means contact is failing. """
        campaign = self.campaign.with_env(self.env)
        test_records = self.test_records.with_env(self.env)
        test_records_ok = self.test_records_ok.with_env(self.env)
        test_records_ko = self.test_records_ko.with_env(self.env)
        bounced = test_records_ok[:2]  # always post update
        failed = test_records_ok[2:4]  # fails at sending
        post_failed = test_records_ok[4]  # fails as post update

        self._launch_campaign(campaign, date_reference=self.date_reference)

        # First traces are processed, email, SMSes and WA msgs are sent (or failed)
        # see 'test_reaction_triggers' that has the same beginning, with more asserts
        date_send = self.date_reference + timedelta(hours=1)  # ok for send mailing
        date_opened = date_send + timedelta(hours=2)  # simulating opened
        with self.mock_datetime_and_now(date_send), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mock_send_email_delivery_exception(failed.mapped('email_from'), error="OutboundSpamException"), \
             self.mockSMSGateway(nbr_t_error={r.phone_sanitized: 'credit' for r in failed}):
            campaign._execute_activities()

        # simulate bounce / fail: should cancel part of sibling traces that are made irrelevant
        for action, action_sa, canceled_siblings in (
            # mail
            (
                "mail_bounce", self.activity_sa_mail_bounce,
                [self.activity_sa_mail_open, self.activity_sa_mail_reply, self.activity_sa_mail_click, self.activity_mail_activity]
            ),
            # sms
            (
                "sms_bounce", self.activity_sa_sms_bounce,
                [self.activity_sa_sms_click, self.activity_sms_activity]
            ),
            # whatsapp
            (
                "whatsapp_bounce", self.activity_sa_wa_bounce,
                [self.activity_sa_wa_read, self.activity_sa_wa_reply, self.activity_sa_wa_click, self.activity_wa_activity]
            ),
        ):
            with self.mock_datetime_and_now(date_opened):
                for record in bounced:
                    if action == "mail_bounce":
                        self.gateway_mail_trace_bounce(self.activity_begin_mail.mass_mailing_id, record)
                        state_msg = 'Parent activity mail bounced'
                    elif action == "sms_bounce":
                        self.gateway_sms_bounce(self.activity_begin_sms.mass_mailing_id, record, error_code='invalid_destination')
                        state_msg = 'Parent activity SMS bounced'
                    elif action == "whatsapp_bounce":
                        self.whatsapp_msg_bounce_with_records(record, error_code=131026)
                        state_msg = 'Parent whatsapp message bounced'
                # note that fail is not a trigger currently, hence do not change anything
                for record in post_failed:
                    if action == "mail_bounce":
                        self.gateway_mail_trace_fail(self.activity_begin_mail.mass_mailing_id, record, failure_reason="Error without exception.", failure_type='unknown')
                        state_msg = 'Parent activity mail bounced'
                    if action == "sms_bounce":
                        self.gateway_sms_failed(self.activity_begin_sms.mass_mailing_id, record, error_code='not_delivered')
                        state_msg = 'Parent activity SMS bounced'
                    # TDE TODO: add other whatsapp reaction checks

            self.assertMarketAutoTraces(
                [{
                    'records': bounced,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': date_opened + timedelta(days=1),
                        'state_msg': False,
                    },
                }, {
                    'records': test_records - bounced,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': False,
                        'state_msg': False,
                    },
                }],
                action_sa,
            )
            for sibling in (action_sa.parent_id.child_ids - action_sa):
                # only "mail_open", "mail_reply", "mail_click", and "activity" are canceled for 'bounce'
                if sibling in canceled_siblings:
                    trace_bounced = bounced
                else:
                    trace_bounced = bounced.browse()
                trace_other = test_records - trace_bounced
                self.assertMarketAutoTraces(
                    [{
                        'records': trace_bounced,
                        'status': 'canceled',
                        'fields_values': {
                            'schedule_date': date_opened,
                            'state_msg': state_msg,
                        },
                    }, {
                        'records': trace_other,
                        'status': 'scheduled',
                    }],
                    sibling,
                )

        # parent (mail / sms / WA sending) action update
        self.assertMarketAutoTraces(
            [{
                'records': test_records_ok - (bounced + failed + post_failed),
                'records_to_partner': {r.id: r.customer_id for r in (test_records_ok - (bounced + failed))},
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': False,
                },
                'trace_status': 'sent',
            }, {
                'records': failed,
                'records_to_partner': {r.id: r.customer_id for r in failed},
                'status': 'error',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'Email failed',
                },
                'trace_failure_reason': "OutboundSpamException",
                'trace_failure_type': 'mail_spam',
                'trace_status': 'error',
            }, {
                'records': post_failed,
                'records_to_partner': {r.id: r.customer_id for r in post_failed},
                'status': 'error',
                'fields_values': {
                    'schedule_date': date_opened,  # set_failed updated schedule_date to error dt, unsure this is right
                    'state_msg': 'Email failed',
                },
                'trace_failure_reason': "Error without exception.",
                'trace_failure_type': 'unknown',
                'trace_status': 'error',
            }, {
                'records': bounced,
                'records_to_partner': {r.id: r.customer_id for r in bounced},
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': False,
                },
                'mail_values': {  # note that bounce did not update the mail.mail itself, only the trace
                    'failure_reason': False,
                    'failure_type': False,
                    'state': 'sent',
                },
                'trace_failure_reason': 'This is the bounce email',
                'trace_failure_type': 'mail_bounce',
                'trace_status': 'bounce',
            }, {
                'records': test_records_ko,
                'status': 'canceled',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'Email cancelled',
                },
                'trace_failure_type': 'mail_email_missing',
                'trace_status': 'cancel',
            }],
            self.activity_begin_mail,
        )
        self.assertMarketAutoTraces(
            [{
                'records': (test_records_ok - (bounced + failed + post_failed)),
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': False,
                },
                'trace_status': 'pending',  # forced send
            }, {
                'records': failed,
                'status': 'error',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'SMS failed',
                },
                'trace_failure_reason': False,
                'trace_failure_type': 'sms_credit',
                'trace_status': 'error',
            }, {
                'records': post_failed,
                'status': 'error',
                'fields_values': {
                    'schedule_date': date_opened,  # set_failed updated schedule_date to error dt, unsure this is right
                    'state_msg': 'SMS failed',
                },
                'sms_values': {  # async fail does not update sms.sms values itself (generally unlinked anyway)
                    'failure_type': False,
                    'state': 'pending',
                },
                'trace_failure_reason': False,
                'trace_failure_type': 'sms_not_delivered',
                'trace_status': 'error',
            }, {
                'records': bounced,
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': False,
                },
                'sms_values': {  # bounce does not update sms.sms values itself (generally unlinked anyway)
                    'failure_type': False,
                    'state': 'pending',
                },
                'trace_failure_reason': False,  # FIXME nothing logged ?
                'trace_failure_type': 'sms_invalid_destination',
                'trace_status': 'bounce',
            }, {
                'records': test_records_ko,
                'status': 'canceled',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'SMS cancelled',
                },
                'trace_failure_type': 'sms_number_missing',
                'trace_status': 'cancel',
            }],
            self.activity_begin_sms,
        )
        self.assertMarketAutoTraces(
            [{
                'records': (test_records_ok - bounced),
                'status': 'processed',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                },
                'trace_content': "<p>Hello your much wow template value</p>",
                'trace_status': 'sent',
            }, {
                'records': bounced,
                'status': 'canceled',  # FIXME: contrary to mail / sms, bounce = canceled
                'fields_values': {
                    'schedule_date': date_opened,  # update at failing dt
                    'state_msg': 'WhatsApp canceled',
                },
                'trace_failure_reason': '131026 : Message failed to send due to an unknown error.',
                'trace_failure_type': 'whatsapp_unrecoverable',
                'trace_status': 'bounce',
            }, {
                'records': test_records_ko,
                'status': 'error',
                'fields_values': {
                    'schedule_date': self.date_reference + timedelta(hours=1),
                    'state_msg': 'WhatsApp failed',
                },
                'trace_content': "<p>Hello your much wow template value</p>",
                'trace_failure_type': 'phone_invalid',
                'trace_status': 'error',
            }],
            self.activity_begin_wa,
        )

    @users('user_marketing_automation')
    def test_reaction_triggers_collect_reply_early_end(self):
        """ Test 'collect_reply' trigger behavior, which means a campaign
        branch scheduled anytime a reply is collected.

        Hierarchy
        - activity_begin_mail (setup) -> will be processed
          - activity_mail_activity (setup) -> will be processed
            - activity_mail_activity_child_orphan (new) -> will be scheduled and canceled
          - activity_begin_mail_child (new) -> will be scheduled
        - collect_reply_activity_1
        - collect_reply_activity_2
        """
        campaign = self.campaign.with_env(self.env)
        campaign.write({'collect_reply_early_end': True})
        test_records = self.test_records.with_env(self.env)
        reply_records = test_records[:2]

        with self.mock_datetime_and_now(self.date_reference):
            # new child of activity_begin_mail
            activity_begin_mail_child = self._create_activity_log_note(
                campaign,
                act_values={
                    'interval_number': 6,
                    'interval_type': 'hours',
                    'log_note_body': "This will be logged",
                    'name': "Log a note: Cancelled 1",
                    'parent_id': self.activity_begin_mail.id,
                    'trigger_type': 'activity',
                },
            )
            # grand-child of activity_begin_mail via activity_mail_activity
            activity_mail_activity_child_orphan = self._create_activity_log_note(
                campaign, act_values={
                    'interval_number': 2,
                    'interval_type': 'days',
                    'log_note_body': "This won't be logged either",
                    'name': "Log a note: Cancelled 2",
                    'parent_id': self.activity_mail_activity.id,
                    'trigger_type': 'activity',
                },
            )
            collect_reply_activity_1 = self._create_activity_mail(campaign, act_values={
                "interval_type": 'days',
                "interval_number": 1,
                "name": "Mail Activity Collect",
                "parent_id": False,
                "trigger_type": "collect_reply",
            })
            collect_reply_activity_2 = self._create_activity_mail(campaign, act_values={
                "interval_type": 'days',
                "interval_number": 2,
                "name": "Mail Activity Collect",
                "parent_id": False,
                "trigger_type": "collect_reply",
            })
            self._launch_campaign(campaign, self.date_reference)

        self.assertActivityWoTrace(
            self.activity_mail_activity + activity_begin_mail_child +
            activity_mail_activity_child_orphan + collect_reply_activity_1 + collect_reply_activity_2
        )
        date_begin = self.date_reference + timedelta(hours=3)
        date_second = self.date_reference + timedelta(hours=4)
        date_subaction = date_begin + timedelta(days=1)

        # execute begin activity
        with self.mock_datetime_and_now(date_begin), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mockSMSGateway():
            campaign.action_execute_activities()

        self.assertMarketAutoTraces([
            {
                'records': self.test_records_ok,
                'quick': True,
                'status': 'processed',
            }, {
                'records': self.test_records_ko,
                'quick': True,
                'status': 'canceled',
            }], self.activity_begin_mail)
        # child of activity_begin_mail are scheduled
        self.assertMarketAutoTraces([{
            'fields_values': {
                'schedule_date': date_begin,
            },
            'records': test_records,
            'status': 'scheduled'
        }], self.activity_mail_activity)
        self.assertMarketAutoTraces([{
            'fields_values': {
                'schedule_date': self.date_reference + timedelta(hours=7),  # TDE note: strange hour delay ?
            },
            'records': test_records,
            'status': 'scheduled'
        }], activity_begin_mail_child)
        self.assertActivityWoTrace(activity_mail_activity_child_orphan + collect_reply_activity_1 + collect_reply_activity_2)

        # execute first children of begin activity (allowing to test descendants in addition to direct children)
        with self.mock_datetime_and_now(date_second), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mockSMSGateway():
            campaign.action_execute_activities()

        self.assertMarketAutoTraces([
            {
                'records': self.test_records_ok,
                'quick': True,
                'status': 'processed',
            }, {
                'records': self.test_records_ko,
                'quick': True,
                'status': 'canceled',
            }], self.activity_begin_mail)
        # child of activity_begin_mail are scheduled
        self.assertMarketAutoTraces([{
            'records': test_records,
            'quick': True,
            'status': 'processed'
        }], self.activity_mail_activity)
        self.assertMarketAutoTraces([{
            'records': test_records,
            'quick': True,
            'status': 'scheduled'
        }], activity_begin_mail_child)
        self.assertMarketAutoTraces([{
            'records': test_records,
            'quick': True,
            'status': 'scheduled'
        }], activity_mail_activity_child_orphan)
        self.assertActivityWoTrace(collect_reply_activity_1 + collect_reply_activity_2)

        with self.mock_datetime_and_now(date_subaction):
            self.gateway_mail_trace_reply(MAIL_TEMPLATE, self.activity_begin_mail.mass_mailing_id, reply_records)

        self.assertMarketAutoTraces(
            [{
                "records": reply_records,
                "status": "scheduled",
                "fields_values": {
                    "schedule_date": date_subaction + timedelta(days=1),
                },
            }],
            collect_reply_activity_1,
        )
        self.assertMarketAutoTraces(
            [{
                "records": reply_records,
                "status": "scheduled",
                "fields_values": {
                    "schedule_date": date_subaction + timedelta(days=2),
                },
            }],
            collect_reply_activity_2,
        )
        for to_check in activity_begin_mail_child + activity_mail_activity_child_orphan:
            with self.subTest(activity_name=to_check.name):
                self.assertMarketAutoTraces([{
                    "records": test_records - reply_records,
                    "status": "scheduled",
                }, {
                    "records": reply_records,
                    "status": "canceled",
                }], to_check)

    def test_reaction_triggers_collect_reply_early_end_on_old_reply(self):
        campaign = self.campaign.with_env(self.env)
        campaign.write({'collect_reply_early_end': True})
        test_records = self.test_records.with_env(self.env)
        reply_records = test_records[:2]

        with self.mock_datetime_and_now(self.date_reference):
            orphan_activity_to_cancel = self._create_activity_log_note(campaign, act_values={
                    'interval_type': 'hours',
                    'interval_number': 1,
                    "log_note_body": "This won't be logged",
                    "name": "Log a note: Cancelled",
                    "parent_id": self.activity_mail_activity.id,
                    "trigger_type": 'activity',
            })
            collect_reply_activity = self._create_activity_mail(campaign, act_values={
                "interval_type": "days",
                "interval_number": 1,
                "name": "Mail Activity Collect",
                "parent_id": False,
                "trigger_type": "collect_reply",
            })
            self._launch_campaign(campaign, self.date_reference)

        date_opened = self.date_reference + timedelta(hours=3)
        date_subaction = date_opened + timedelta(days=1)

        with self.mock_datetime_and_now(date_subaction), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mockSMSGateway():
            # send the begin email
            campaign.action_execute_activities()
            # process the child activities
            campaign.action_execute_activities()

        self.assertMarketAutoTraces([
            {
                'records': self.test_records_ok,
                'quick': True,
                'status': 'processed',
            }, {
                'records': self.test_records_ko,
                'quick': True,
                'status': 'canceled',
            }], self.activity_begin_mail)
        self.assertMarketAutoTraces([{
            'records': test_records,
            'status': 'processed'
        }], self.activity_mail_activity)
        self.assertMarketAutoTraces([{
            'records': test_records,
            'status': 'scheduled',
        }], orphan_activity_to_cancel)
        self.assertActivityWoTrace(collect_reply_activity)

        # now we reply to the old email
        with self.mock_datetime_and_now(date_subaction):
            self.gateway_mail_trace_reply(MAIL_TEMPLATE, self.activity_begin_mail.mass_mailing_id, reply_records)

        self.assertMarketAutoTraces([{
            "records": reply_records,
            "status": 'scheduled',
            "fields_values": {
                "schedule_date": date_subaction + timedelta(days=1),
            }
        }], collect_reply_activity)
        self.assertMarketAutoTraces([{
            "records": reply_records,
            "status": 'canceled',
        }, {
            "records": test_records - reply_records,
            "status": 'scheduled',
        }], orphan_activity_to_cancel)

    @users('user_marketing_automation')
    def test_reaction_triggers_multiple(self):
        """ Test multiple triggers (e.g. several replies) do not trigger
        child traces several times. """
        campaign = self.campaign.with_env(self.env)
        test_records = self.test_records.with_env(self.env)
        test_records_ok = self.test_records_ok.with_env(self.env)

        self.test_reaction_triggers()

        date_opened = self.date_reference + timedelta(hours=1) + timedelta(hours=2)  # see previous test
        date_subaction = date_opened + timedelta(days=1)

        # now that some records have been opened / replied / clicked, we can process
        # sub activities linked to those triggers
        with self.mock_datetime_and_now(date_subaction), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mockSMSGateway():
            campaign._execute_activities()

        todo = test_records_ok[:5]
        for subaction in (
            # mail
            self.activity_sa_mail_open, self.activity_sa_mail_reply, self.activity_sa_mail_click,
            # sms
            self.activity_sa_sms_click,
            # whatsapp
            self.activity_sa_wa_read, self.activity_sa_wa_reply, self.activity_sa_wa_click, self.activity_sa_wa_click,
        ):
            with self.subTest(subaction_name=subaction.name):
                self.assertMarketAutoTraces(
                    [{
                        'records': todo,
                        'status': 'processed',
                        'fields_values': {
                            'schedule_date': date_subaction,
                            'state_msg': False,
                        },
                    }, {
                        'records': test_records - todo,
                        'status': 'scheduled',
                        'fields_values': {
                            'schedule_date': False,
                        },
                    }],
                    subaction,
                )

        # receive replies again, check traces are still processed and not set
        # back to schedule
        # Simulate open / reply / click
        # - active traces should be processed, schedule date updated
        # - opposite traces should be canceled
        for action, action_sa, opposite_sa in (
            # mail
            ("mail_open", self.activity_sa_mail_open, self.activity_sa_mail_not_open),
            ("mail_reply", self.activity_sa_mail_reply, self.activity_sa_mail_not_reply),
            ("mail_click", self.activity_sa_mail_click, self.activity_sa_mail_not_click),
            # sms
            ("sms_click", self.activity_sa_sms_click, self.activity_sa_sms_not_click),
            # whatsapp
            ("whatsapp_open", self.activity_sa_wa_read, self.activity_sa_wa_not_read),
            ("whatsapp_reply", self.activity_sa_wa_reply, self.activity_sa_wa_not_reply),
            # ("whatsapp_click", self.activity_sa_wa_click, self.activity_sa_wa_not_click),  # tool not supporting it
        ):
            todo = test_records_ok[:5]
            with self.subTest(action=action):
                with self.mock_datetime_and_now(date_opened):
                    for record in todo:
                        if action == "mail_open":
                            self.gateway_mail_trace_open(self.activity_begin_mail.mass_mailing_id, record)
                        elif action == "mail_reply":
                            self.gateway_mail_trace_reply(MAIL_TEMPLATE, self.activity_begin_mail.mass_mailing_id, record)
                        elif action == "mail_click":
                            self.gateway_mail_trace_click_simple(self.activity_begin_mail.mass_mailing_id, record)
                        elif action == "sms_click":
                            self.gateway_sms_click_simple(self.activity_begin_sms.mass_mailing_id, record)
                        elif action == "whatsapp_open":
                            self.whatsapp_msg_read_with_records(record, find_in_mock=False, mock=False)
                        elif action == "whatsapp_reply":
                            self.whatsapp_answer_with_records(record, find_in_mock=False, mock=False)
                        elif action == "whatsapp_click":
                            self.whatsapp_msg_click_with_records(record, button_index=0)
                self.assertMarketAutoTraces(
                    [{
                        'records': todo,
                        'status': 'processed',  # should not be back to scheduled
                        'fields_values': {
                            'schedule_date': date_subaction,
                        },
                    }, {
                        'records': test_records - todo,
                        'status': 'scheduled',
                        'fields_values': {
                            'schedule_date': False,
                        },
                    }],
                    action_sa,
                )
                self.assertMarketAutoTraces(
                    [{
                        'records': todo,
                        'status': 'canceled',
                    }, {
                        'records': test_records - todo,
                        'status': 'scheduled',
                    }],
                    opposite_sa,
                )

    @users('user_marketing_automation')
    def test_schedule_date_based_on_triggers_new(self):
        """ Test triggers when adding a new activity """
        self._launch_campaign(self.campaign)
        date_send = self.date_reference + timedelta(hours=1)

        with self.mock_datetime_and_now(date_send), self.mock_mail_gateway():
            self.campaign._execute_activities()

        # add a new begin activity
        new_activity = self._create_activity_mail(
            self.campaign, self.env.user,
            act_values={
                "interval_number": 1,
                "interval_type": "days",
                "trigger_type": "begin",
            },
        )

        # add new participants that should have traces for the begin activities
        # so that we also check they are not duplicated at rescheduling
        new_test_records = self._create_marketauto_records(model='marketing.test.sms', count=1)
        self.campaign.write({"enroll_domain": [("id", "in", (self.test_records + new_test_records).ids)]})
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=3)):
            self.campaign._synchronize_participants()
        self.assertMarketAutoTraces(
            [{
                "records": new_test_records,
                "status": "scheduled",
                "fields_values": {
                    "schedule_date": self.date_reference + timedelta(days=1, hours=3),
                },
            }],
            new_activity,
        )
        for activity in (
            self.activity_begin_mail + self.activity_begin_sms +
            self.activity_begin_wa + self.activity_begin_sa
        ):
            self.assertMarketAutoTraces(
                [{
                    "records": new_test_records,
                    "status": "scheduled",
                    "fields_values": {
                        "schedule_date": self.date_reference + timedelta(hours=4),  # sync date + activity timedelta
                    },
                }],
                activity,
                strict=False,
            )

    @mute_logger('odoo.addons.mail.models.mail_mail')
    @users('user_marketing_automation')
    def test_schedule_date_based_on_triggers_update(self):
        """ Test triggers when updating activities """
        self._launch_campaign(self.campaign, date_reference=self.date_reference)
        date_send = self.date_reference + timedelta(hours=1)
        date_subaction = date_send + timedelta(days=5)

        with self.mock_datetime_and_now(date_send), self.mock_mail_gateway():
            self.campaign._execute_activities()

        # changing already-done activities: should not impact anything as child
        # traces are based upon parent traces, already done
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=2)):
            (
                self.activity_begin_mail + self.activity_begin_sms +
                self.activity_begin_wa + self.activity_begin_sa
            ).write({
                "interval_number": 2,
                "interval_type": "days",
            })
            self.campaign._synchronize_traces()

        for sub_activity, expected_schedule_date in [
            # mail
            (self.activity_sa_mail_not_open, date_subaction),
            (self.activity_sa_mail_open, False),  # mail open: no date, as user input
            (self.activity_sa_mail_not_reply, date_subaction),
            (self.activity_sa_mail_reply, False),  # mail reply: no date, as user input
            (self.activity_sa_mail_not_click, date_subaction),
            (self.activity_sa_mail_click, False),  # mail click: no date, as user input
            (self.activity_sa_mail_bounce, False),  # mail bounce: no date, as user input
            # sms
            (self.activity_sa_sms_not_click, date_subaction),
            (self.activity_sa_sms_click, False),  # sms click: no date, as user input
            (self.activity_sa_sms_bounce, False),  # sms bounce: no date, as user input
            # whatsapp
            (self.activity_sa_wa_not_read, date_subaction),
            (self.activity_sa_wa_read, False),  # wa read: no date, as user input
            (self.activity_sa_wa_not_reply, date_subaction),
            (self.activity_sa_wa_reply, False),  # wa replied: no date, as user input
            (self.activity_sa_wa_not_click, date_subaction),
            (self.activity_sa_wa_click, False),  # wa click: no date, as user input
            (self.activity_sa_wa_bounce, False),  # wa bounce: no date, as user input
            # other
            (self.activity_mail_activity, date_send + timedelta(hours=2)),
            (self.activity_sms_activity, date_send + timedelta(hours=2)),
            (self.activity_wa_activity, date_send + timedelta(hours=2)),
        ]:
            self.assertMarketAutoTraces(
                [{
                    'records': self.test_records,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': expected_schedule_date,
                    },
                }],
                sub_activity,
            )

        # change scheduled activities: should not impact "no deadline" activities
        # such as mail_open, mail_click as they depend on user action
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=3)):
            (
                # mail
                self.activity_sa_mail_not_open + self.activity_sa_mail_open +
                self.activity_sa_mail_not_reply + self.activity_sa_mail_reply +
                self.activity_sa_mail_not_click + self.activity_sa_mail_click +
                self.activity_sa_mail_bounce +
                # sms
                self.activity_sa_sms_not_click + self.activity_sa_sms_click +
                self.activity_sa_sms_bounce +
                # whatsapp
                self.activity_sa_wa_not_read + self.activity_sa_wa_read +
                self.activity_sa_wa_not_reply + self.activity_sa_wa_reply +
                self.activity_sa_wa_not_click + self.activity_sa_wa_click +
                self.activity_sa_wa_bounce +
                # other
                self.activity_mail_activity + self.activity_sms_activity + self.activity_wa_activity
            ).write({
                "interval_number": 2,
                "interval_type": "days",
            })
            self.campaign._synchronize_traces()
        date_subaction = date_send + timedelta(days=2)

        for sub_activity, expected_schedule_date in [
            # mail
            (self.activity_sa_mail_not_open, date_subaction),
            (self.activity_sa_mail_open, False),  # mail open: no date, as user input
            (self.activity_sa_mail_not_reply, date_subaction),
            (self.activity_sa_mail_reply, False),  # mail reply: no date, as user input
            (self.activity_sa_mail_not_click, date_subaction),
            (self.activity_sa_mail_click, False),  # mail click: no date, as user input
            (self.activity_sa_mail_bounce, False),  # mail bounce: no date, as user input
            # sms
            (self.activity_sa_sms_not_click, date_subaction),
            (self.activity_sa_sms_click, False),  # sms click: no date, as user input
            (self.activity_sa_sms_bounce, False),  # sms bounce: no date, as user input
            # whatsapp
            (self.activity_sa_wa_not_read, date_subaction),
            # (self.activity_sa_wa_read, False),  # wa read: no date, as user input
            (self.activity_sa_wa_not_reply, date_subaction),
            # (self.activity_sa_wa_reply, False),  # wa reply: no date, as user input
            (self.activity_sa_wa_not_click, date_subaction),
            (self.activity_sa_wa_click, False),  # wa click: no date, as user input
            (self.activity_sa_wa_bounce, False),  # wa bounce: no date, as user input
            # other
            (self.activity_mail_activity, date_subaction),
            (self.activity_sms_activity, date_subaction),
            (self.activity_wa_activity, date_subaction),
        ]:
            self.assertMarketAutoTraces(
                [{
                    'records': self.test_records,
                    'status': 'scheduled',
                    'fields_values': {
                        'schedule_date': expected_schedule_date,
                    },
                }],
                sub_activity,
            )

        # update write_date on some traces by triggering trace update
        new_now = self.date_reference + timedelta(hours=5)
        date_subaction_new = new_now + timedelta(days=2)
        with self.mock_datetime_and_now(new_now):
            self.gateway_mail_trace_open(self.activity_begin_mail.mass_mailing_id, self.test_records[0])
            self.gateway_mail_trace_reply(MAIL_TEMPLATE, self.activity_begin_mail.mass_mailing_id, self.test_records[1])
            self.gateway_mail_trace_click(self.activity_begin_mail.mass_mailing_id, self.test_records[2], "LINK")

        for record, sub_activity, exp_status, exp_schedule_date in [
            # mail
            (self.test_records[0], self.activity_sa_mail_not_open, "canceled", new_now),
            (self.test_records[0], self.activity_sa_mail_open, "scheduled", date_subaction_new),
        ]:
            self.assertMarketAutoTraces(
                [{
                    'records': record,
                    'status': exp_status,
                    'fields_values': {
                        'schedule_date': exp_schedule_date,
                    },
                }],
                sub_activity,
                strict=False,
            )

        # update sub actions, updated date should be based on trace date
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=3)):
            (
                # mail
                self.activity_sa_mail_not_open + self.activity_sa_mail_open +
                self.activity_sa_mail_not_reply + self.activity_sa_mail_reply +
                self.activity_sa_mail_not_click + self.activity_sa_mail_click +
                self.activity_sa_mail_bounce +
                # sms
                self.activity_sa_sms_not_click + self.activity_sa_sms_click +
                self.activity_sa_sms_bounce +
                # whatsapp
                self.activity_sa_wa_not_read + self.activity_sa_wa_read +
                self.activity_sa_wa_not_reply + self.activity_sa_wa_reply +
                self.activity_sa_wa_not_click + self.activity_sa_wa_click +
                self.activity_sa_wa_bounce
            ).write({
                "interval_number": 5,
                "interval_type": "days",
            })
            self.campaign._synchronize_traces()
        date_subaction_upd = new_now + timedelta(days=5)

        for record, sub_activity, exp_status, exp_schedule_date in [
            # opened mail
            (self.test_records[0], self.activity_sa_mail_not_open, "canceled", new_now),
            (self.test_records[0], self.activity_sa_mail_open, "scheduled", date_subaction_upd),
            (self.test_records[0], self.activity_sa_mail_not_reply, "scheduled", date_subaction_upd - timedelta(hours=4)),  # still cheduled on opened mail, also unsure those hours ??
            (self.test_records[0], self.activity_sa_mail_reply, "scheduled", False),  # user input, should not be scheduled
            # replied mail
            (self.test_records[1], self.activity_sa_mail_not_open, "canceled", new_now),
            (self.test_records[1], self.activity_sa_mail_open, "scheduled", date_subaction_upd),  # mail open: shoudln't it be no date, as user input ?
            (self.test_records[1], self.activity_sa_mail_not_reply, "canceled", new_now),
            (self.test_records[1], self.activity_sa_mail_reply, "scheduled", date_subaction_upd),  # date_subaction_new ?
        ]:
            self.assertMarketAutoTraces(
                [{
                    'records': record,
                    'status': exp_status,
                    'fields_values': {
                        'schedule_date': exp_schedule_date,
                    },
                }],
                sub_activity,
                strict=False,
            )

    @users('user_marketing_automation')
    def test_updating_activity_hierarchy(self):
        """ Test activity hierarchy updates are restricted when traces exist """
        self._launch_campaign(self.campaign, date_reference=self.date_reference)
        date_send = self.date_reference + timedelta(hours=1)

        self.assertTrue(self.activity_begin_sms.trace_ids)
        with self.assertRaises(ValidationError):
            self.activity_begin_sms.write({
                "trigger_type": "activity",
                "parent_id": self.activity_begin_mail,
            })

        self.assertFalse(self.activity_mail_activity.trace_ids)
        with self.mock_datetime_and_now(date_send):
            self.activity_mail_activity.write({
                "trigger_type": "activity",
                "parent_id": self.activity_begin_sms,
            })
            self.activity_begin_sms.execute()
        self.assertMarketAutoTraces(
            [{
                "records": self.test_records,
                "status": "scheduled",
                "fields_values": {
                    "schedule_date": date_send + timedelta(hours=2),
                },
            }],
            self.activity_mail_activity,
            strict=True,
        )

    @users('user_marketing_automation')
    def test_updating_activity_parent_in_test(self):
        """ Test activity hierarchy updates with test traces """
        self.campaign.enroll_domain = [(0, '=', 1)]
        self._launch_campaign(self.campaign, date_reference=self.date_reference)

        self.env['marketing.campaign.test'].create({
            'campaign_id': self.campaign.id,
            'res_id': self.test_records[0].id,
        }).action_launch_test()

        self.assertEqual(len(self.activity_begin_sms.trace_ids), 1)
        test_trace = self.activity_begin_sms.trace_ids[0]
        self.assertEqual(test_trace.state, 'scheduled')

        self.activity_begin_sms.write({
            'trigger_type': 'activity',
            'parent_id': self.activity_begin_mail,
            'interval_number': 5,
            'interval_type': 'days',
        })
        self.assertTrue(self.activity_begin_sms.require_sync)

        self.campaign._synchronize_traces()
        expected_date = test_trace.participant_id.create_date + timedelta(days=5)
        self.assertEqual(test_trace.schedule_date, expected_date)


@tagged('marketing_automation', 'ma_sync')
class TestSynchronize(ActivityTriggersCase):

    @mute_logger('odoo.addons.mail.models.mail_thread')
    @users('user_marketing_automation')
    def test_post_launch_synchronize(self):
        """ Test participants creation then update when adding new activities
        on a running campaign. We should not duplicate traces, notably when
        a participant had traces on a new activity that is then updated
        automatically. """
        campaign = self.env['marketing.campaign'].create({
            'enroll_domain': [('id', 'in', self.test_records.ids)],
            'model_id': self.env['ir.model']._get_id('marketing.test.sms'),
            'name': 'Test Campaign',
        })
        # begin activities, parents for each type category to test
        activity_begin_mail = self._create_activity(
            campaign,
            create_date=self.date_reference,
            mailing=self.test_mailing_mail,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )
        activity_begin_sms = self._create_activity(
            campaign,
            create_date=self.date_reference,
            mailing=self.test_mailing_sms,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )
        activity_begin_wa = self._create_activity(
            campaign,
            create_date=self.date_reference,
            wa_template=self.test_wa_template,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )
        _activity_begin_sa = self._create_activity(
            campaign,
            create_date=self.date_reference,
            action=self.test_sa_descr_action,
            interval_number=1, interval_type='hours',
            trigger_type='begin',
        )

        # init participants and traces
        with self.mock_datetime_and_now(self.date_reference):
            self._launch_campaign(campaign, self.date_reference)
            campaign._synchronize_traces()
        # run begin activities so that we have traces for replies / ...
        with self.mock_datetime_and_now(self.date_reference + timedelta(hours=1)), \
             self.mockWhatsappGateway(), self.patchWhatsappCronTrigger(), \
             self.mock_mail_gateway(), self.mockSMSGateway():
            campaign._execute_activities()

        for parent, existing, additional, exp_assert_values in (
            # mail: records 0-1 are open, 2-3 are replied to, 6-7 are clicked, 8 is bounced
            # ------------------------------------------------------------
            (
                activity_begin_mail,
                ("mail_not_open", self.test_sa_descr_mail_not_open, 0),
                (
                    ("mail_open", self.test_sa_descr_mail_open),
                    ("mail_reply", self.test_sa_descr_mail_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # open still holds, unsure
                    }, {
                        'records': self.test_records_ok,  # reply still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_mail,
                ("mail_open", self.test_sa_descr_mail_open, 0),
                (
                    ("mail_not_open", self.test_sa_descr_mail_not_open),
                    ("mail_not_reply", self.test_sa_descr_mail_not_reply),
                ),
                (
                    {
                        'records': self.test_records_ok[4] + self.test_records_ok[7:],  # not_open canceled by open - note that reply and click implies open
                    }, {
                        'records': self.test_records_ok,  # not_reply still holds even if opened
                    },
                ),
            ),
            (
                activity_begin_mail,
                ("mail_not_reply", self.test_sa_descr_mail_not_reply, 0),
                (
                    ("mail_open", self.test_sa_descr_mail_open),
                    ("mail_reply", self.test_sa_descr_mail_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # open still holds, unsure
                    }, {
                        'records': self.test_records_ok,  # reply still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_mail,
                ("mail_reply", self.test_sa_descr_mail_reply, 0),
                (
                    ("mail_not_open", self.test_sa_descr_mail_not_open),
                    ("mail_not_reply", self.test_sa_descr_mail_not_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # not_open still holds even if replied (to fix probably)
                    }, {
                        'records': self.test_records_ok[:2] + self.test_records_ok[4:],  # not_reply canceled by reply
                    },
                ),
            ),
            (
                activity_begin_mail,
                ("mail_not_click", self.test_sa_descr_mail_not_click, 0),
                (
                    ("mail_open", self.test_sa_descr_mail_open),
                    ("mail_reply", self.test_sa_descr_mail_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # open still holds, unsure
                    }, {
                        'records': self.test_records_ok,  # reply still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_mail,
                ("mail_click", self.test_sa_descr_mail_click, 0),
                (
                    ("mail_not_open", self.test_sa_descr_mail_not_open),
                    ("mail_not_reply", self.test_sa_descr_mail_not_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # not_open still holds even if clicked (to fix probably)
                    }, {
                        'records': self.test_records_ok,  # not_reply still holds
                    },
                ),
            ),
            (
                activity_begin_mail,
                ("mail_bounce", self.test_sa_descr_mail_bounce, 0),
                (
                    ("mail_open", self.test_sa_descr_mail_open),
                    ("mail_not_open", self.test_sa_descr_mail_not_open),
                ),
                (
                    {
                        'records': self.test_records_ok,  # open still holds even if bounced (to check)
                    }, {
                        'records': self.test_records_ok,  # not_reply still holds
                    },
                ),
            ),
            # sms
            # ------------------------------------------------------------
            (
                activity_begin_sms,
                ("sms_not_click", self.test_sa_descr_sms_not_click, 0),
                (
                    ("sms_click", self.test_sa_descr_sms_click),
                ),
                (
                    {
                        'records': self.test_records_ok,  # click still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_sms,
                ("sms_click", self.test_sa_descr_sms_click, 0),
                (
                    ("sms_not_click", self.test_sa_descr_sms_not_click),
                ),
                (
                    {
                        'records': self.test_records_ok[2:],  # not_click canceled by click
                    },
                ),
            ),
            (
                activity_begin_sms,
                ("sms_bounce", self.test_sa_descr_sms_bounce, 0),
                (
                    ("sms_click", self.test_sa_descr_sms_click),
                    ("sms_not_click", self.test_sa_descr_sms_not_click),
                ),
                (
                    {
                        'records': self.test_records_ok,  # check me
                    }, {
                        'records': self.test_records_ok,  # check me
                    },
                ),
            ),
            # whatsapp
            # ------------------------------------------------------------
            (
                activity_begin_wa,
                ("whatsapp_not_open", self.test_sa_descr_wa_not_open, 0),
                (
                    ("whatsapp_open", self.test_sa_descr_wa_open),
                ),
                (
                    {
                        'records': self.test_records_ok,  # read still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_wa,
                ("whatsapp_open", self.test_sa_descr_wa_open, 0),
                (
                    ("whatsapp_not_open", self.test_sa_descr_wa_not_open),
                ),
                (
                    {
                        'records': self.test_records_ok[2:],  # not_read canceled by read
                    },
                ),
            ),
            (
                activity_begin_wa,
                ("whatsapp_not_reply", self.test_sa_descr_wa_not_reply, 0),
                (
                    ("whatsapp_open", self.test_sa_descr_wa_open),
                    ("whatsapp_reply", self.test_sa_descr_wa_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # read still holds, unsure
                    }, {
                        'records': self.test_records_ok,  # reply still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_wa,
                ("whatsapp_reply", self.test_sa_descr_wa_reply, 0),
                (
                    ("whatsapp_not_open", self.test_sa_descr_wa_not_open),
                    ("whatsapp_not_reply", self.test_sa_descr_wa_not_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # not_read still holds even if replied (to fix probably)
                    }, {
                        'records': self.test_records_ok,  # FIXME: not_replied should be canceled by read
                    },
                ),
            ),
            (
                activity_begin_wa,
                ("whatsapp_not_click", self.test_sa_descr_wa_not_click, 0),
                (
                    ("whatsapp_open", self.test_sa_descr_wa_open),
                    ("whatsapp_reply", self.test_sa_descr_wa_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # open still holds, unsure
                    }, {
                        'records': self.test_records_ok,  # replied still holds, unsure
                    },
                ),
            ),
            (
                activity_begin_wa,
                ("whatsapp_click", self.test_sa_descr_wa_click, 0),
                (
                    ("whatsapp_not_open", self.test_sa_descr_wa_not_open),
                    ("whatsapp_not_reply", self.test_sa_descr_wa_not_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # not_read still holds even if replied (to fix probably)
                    }, {
                        'records': self.test_records_ok,  # not_replied still holds, logic (clicked, not necessarily replied)
                    },
                ),
            ),
            (
                activity_begin_wa,
                ("whatsapp_bounce", self.test_sa_descr_wa_bounce, 0),
                (
                    ("whatsapp_open", self.test_sa_descr_wa_open),
                    ("whatsapp_not_open", self.test_sa_descr_wa_not_open),
                    ("whatsapp_reply", self.test_sa_descr_wa_reply),
                    ("whatsapp_not_reply", self.test_sa_descr_wa_not_reply),
                ),
                (
                    {
                        'records': self.test_records_ok,  # read still holds even if bounced (to fix probably)
                    }, {
                        'records': self.test_records_ok,  # not_read still holds, unsure
                    }, {
                        'records': self.test_records_ok,  # replied still holds even if bounced (to fix probably)
                    }, {
                        'records': self.test_records_ok,  # not_replied still holds, unsure
                    },
                ),
            ),
        ):
            trigger_type, server_action, interval = existing
            with self.subTest(parent_name=parent.name, trigger_type=trigger_type):
                # create activity, schedule it to have traces
                new_activities = self._create_activity(
                    campaign,
                    create_date=self.date_reference + timedelta(hours=1),
                    action=server_action,
                    interval_number=interval, interval_type='days',
                    parent_id=parent.id,
                    trigger_type=trigger_type,
                )
                with self.mock_datetime_and_now(self.date_reference + timedelta(hours=2)):
                    campaign._synchronize_traces()  # scheduled newly create activity

                if parent.activity_type == 'mail':
                    # update traces: open
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.gateway_mail_trace_open(parent.mass_mailing_id, self.test_records[0:2])
                    # update traces: reply
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.gateway_mail_trace_reply(MAIL_TEMPLATE, parent.mass_mailing_id, self.test_records[2:4])
                    # update traces: click
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.gateway_mail_trace_click(parent.mass_mailing_id, self.test_records[6:8], "LINK")
                    # update traces: bounce
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.gateway_mail_trace_bounce(parent.mass_mailing_id, self.test_records[8])
                elif parent.activity_type == 'sms':
                    # update traces: click
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.gateway_sms_click(parent.mass_mailing_id, self.test_records[0], use_sent_sms=False, sms_status='pending')
                        self.gateway_sms_click(parent.mass_mailing_id, self.test_records[1], use_sent_sms=False, sms_status='pending')
                    # update traces: bounce
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.gateway_sms_bounce(parent.mass_mailing_id, self.test_records[2])
                elif parent.activity_type == 'whatsapp':
                    # update traces: open
                    with self.mock_datetime_and_now(self.date_reference + timedelta(hours=4)):
                        self.whatsapp_msg_read_with_records(self.test_records[0:2])
                else:
                    raise NotImplementedError()

                # add brother-like activity, check status
                for to_create in additional:
                    trigger_type, server_action = to_create
                    new_activities += self._create_activity(
                        campaign,
                        create_date=self.date_reference + timedelta(hours=5),
                        action=server_action,
                        interval_number=1, interval_type='days',
                        parent_id=parent.id,
                        trigger_type=trigger_type,
                    )
                with self.mock_datetime_and_now(self.date_reference + timedelta(hours=8)):
                    campaign._synchronize_traces()

                # final expected status: for parent
                if parent.activity_type == 'mail':
                    self.assertMarketAutoTraces(  # begin mail activity sent for everyone
                        [{
                            'records': self.test_records_ok[0:2],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[0:2]},
                            'status': 'processed',
                            'trace_status': 'open',  # gateway trigerred
                        }, {
                            'records': self.test_records_ok[2:4],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[2:4]},
                            'status': 'processed',
                            'trace_status': 'reply',  # gateway trigerred
                        }, {
                            'records': self.test_records_ok[5:7],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[5:7]},
                            'mailing_trace_values': {
                                'links_click_datetime': self.date_reference + timedelta(hours=4),
                            },
                            'status': 'processed',
                            'trace_status': 'open',  # click is not a status
                        }, {
                            'records': self.test_records_ok[7],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[7]},
                            'status': 'processed',
                            'mail_values': {  # note that bounce did not update the mail.mail itself, only the trace
                                'failure_reason': False,
                                'failure_type': False,
                                'state': 'sent',
                            },
                            'trace_failure_reason': 'This is the bounce email',
                            'trace_failure_type': 'mail_bounce',
                            'trace_status': 'bounce',  # click is not a status
                        }, {
                            'records': self.test_records_ok[4] + self.test_records_ok[8:],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[4] + self.test_records_ok[8:]},
                            'status': 'processed',
                            'trace_status': 'sent',
                        }, {
                            'records': self.test_records_ko,
                            'status': 'canceled',
                            'trace_failure_type': 'mail_email_missing',
                            'trace_status': 'cancel',
                        }],
                        parent,
                    )
                elif parent.activity_type == 'sms':
                    self.assertMarketAutoTraces(  # begin sms activity sent for everyone
                        [{
                            'records': self.test_records_ok[0:2],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[0:2]},
                            'mailing_trace_values': {
                                'links_click_datetime': self.date_reference + timedelta(hours=4),
                            },
                            'sms_values': {
                                'state': 'pending',  # sms_force_send activated, hence not ouggoing
                            },
                            'status': 'processed',
                            'trace_status': 'open',  # click is not a status
                        }, {
                            'check_sms': False,  # sms untouched, still old values (not bounced)
                            'records': self.test_records_ok[2],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[2]},
                            'status': 'processed',
                            'trace_failure_type': 'sms_invalid_destination',
                            'trace_status': 'bounce',
                        }, {
                            'records': self.test_records_ok[3:],
                            'records_to_partner': {r.id: r.customer_id for r in self.test_records_ok[2:4]},
                            'status': 'processed',
                            'trace_status': 'pending',  # sms_force_send activated, hence not outgoing
                        }, {
                            'records': self.test_records_ko,
                            'status': 'canceled',
                            'trace_failure_type': 'sms_number_missing',
                            'trace_status': 'cancel',
                        }],
                        parent,
                    )
                elif parent.activity_type == 'whatsapp':
                    self.assertMarketAutoTraces(  # begin wa activity sent for everyone
                        [{
                            'records': self.test_records_ok[0:2],
                            'status': 'processed',
                            'trace_status': 'read',  # trace_status is actually directly wa message state here
                        }, {
                            'records': self.test_records_ok[2:],
                            'status': 'processed',
                            'trace_status': 'sent',  # trace_status is actually directly wa message state here
                        }, {
                            'records': self.test_records_ko,
                            'status': 'error',
                            'trace_failure_type': 'phone_invalid',
                            'trace_status': 'error',
                        }],
                        parent,
                    )

                # final expected status: for children
                for new_activity, check_values in zip(new_activities[1:], exp_assert_values, strict=True):
                    with self.subTest(new_activity_name=new_activity.name):
                        self.assertMarketAutoTraces(
                            [{
                                'records': self.test_records_ok,
                                'status': 'scheduled',
                                **check_values,
                            }],
                            new_activity,
                        )

                # cleanup
                new_activities.unlink()
                campaign.last_sync_date = self.date_reference
