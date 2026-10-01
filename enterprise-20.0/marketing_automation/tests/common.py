# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from datetime import timedelta

from odoo import fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.addons.mass_mailing.tests.common import MassMailCase, MassMailCommon

_logger = logging.getLogger(__name__)


class MarketingAutomationCase(MassMailCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # store MA crons on cls, always handy to have them available without ref
        cls.cron_ma_sync_participants = cls.env.ref('marketing_automation.ir_cron_campaign_sync_participants')
        cls.cron_ma_execute_activities = cls.env.ref('marketing_automation.ir_cron_campaign_execute_activities')
        cls.cron_ma_check_activities_status = cls.env.ref('marketing_automation.ir_cron_activity_check_activities_status')

        cls.date_reference = fields.Datetime.from_string("2024-07-15 10:30:00")

    def setUp(self):
        super().setUp()
        crons = self.cron_ma_sync_participants + self.cron_ma_execute_activities + self.cron_ma_check_activities_status
        self.env['ir.cron.progress'].search([('cron_id', 'in', crons.ids)]).unlink()
        self.cron_last_call = self.date_reference - timedelta(hours=11)
        crons.write({
            'failure_count': 0,
            'first_failure_date': False,
            'interval_number': 12,
            'interval_type': 'hours',
            'lastcall': self.cron_last_call,
            'nextcall': self.date_reference + timedelta(hours=1),
        })
        self.cron_ma_execute_activities.write({'interval_number': 2})

    # ------------------------------------------------------------
    # TOOLS AND ASSERTS
    # ------------------------------------------------------------

    def assertMarketAutoTraces(self, participants_info, activity, strict=True, canceled_res_ids=None):
        """ Check content of traces.

        :param participants_info: [{
            # participants
            'participants': participants record_set,      # optional: check coherency of expected participants
            'participants_state': string,                 # optional: check linked participants state
            # marketing trace
            'fields_values': dict,                        # optional fields values to check on marketing.trace
            'quick': boolean,                             # just check marketing.trace state then continue (skip mail, ...)
            'status': status,                             # marketing trace status (processed, ...) for all records
            # record info
            'records': records,                           # records going through this activity
            'records_missing': boolean,                   # records have been unlinked due to various reasons -> do not access
            # mailing/sms trace
            'check_mail': boolean,                        # whether to check mail
            'mailing_trace_values': value to check        # propagated to type specific asserts (mail or SMS)
            'trace_content': content of mail/sms          # content of sent mail / sms / whatsapp
            'trace_email': email logged on trace          # may differ from 'email_normalized'
            'trace_email_to_mail': email logged on mail   # for assertMailMail
            'trace_email_to_recipients': email            # for assertSentEmail
            'trace_failure_reason': failure_reason of trace,   # to check message update in case of failure
            'trace_failure_type': failure_type of trace   # to check status update in case of failure
            'trace_status': status of mailing trace,      # if not set: check there is no mailing trace
            'email_values': outgoing email check          # for assertSentEmail
            'mail_values': mail.mail check                # for assertMailMail
            # sms specific (see assertSMSTraces)
            'check_sms': boolean,                         # whether to check SMS
            'sms_values': dict,                           # sms.sms values
            'sent_unlink': boolean,                       # whether sms are unlinked, hence checking IAP mock data directly
            'trace_sms_number': char,                     # 'number' check, fallback on phone_sanitized
            # WA specific
            'wa_from_mock',
            'wa_msg_values',
            # mailing/sms/WA trace, record-specific information
            'records_to_email_to_mail': {rec.id: email},  # override trace_email_to_mail (mail)
            'records_to_email_to_recipients': {rec.id: email},  # override trace_email_to_recipients (mail)
            'records_to_trace_email': {rec.id: email},    # override trace_email (mail)
            'records_to_trace_status': {rec.id: status},  # override of trace_status (mail only)
            'records_to_number': {rec.id: number},        # override of trace_sms_number (SMS / WA)
            'records_to_partner: {rec.id: <res.partner>}, # linked partner (recipient) (mail / WA)
        }, {}, ... ]
        :param activity: a marketing.activity on which marketing traces are about
            to be checked, as well as sub records like mailing.trace if requested
            by status;
        :param strict: whether activity traces must match given records IDs;
        :param canceled_res_ids: quick check for canceled marketing traces not given
            in participants_info (e.g. unlinked records, quick validation, ...);
        """
        all_records, all_records_unlinked = self.env[activity.campaign_id.model_name], self.env[activity.campaign_id.model_name]
        for info in participants_info:
            if not info.get('records_missing'):
                all_records += info['records']
            else:
                all_records_unlinked += info['records']

        # find traces linked to activity, ensure we have one trace / record
        traces = self.env['marketing.trace'].search([
            ('activity_id', 'in', activity.ids),
        ])
        traces_info = [f'Checking for activity {activity.name} ({activity.activity_type}, {activity.trigger_type}, parent {activity.parent_id.name})']
        for trace in traces:
            record = all_records.filtered(lambda r: r.id == trace.res_id)
            record_info = "-no record found in assert-"
            if record:
                record_info = f"ID.{record.id}, {record.display_name}: email {record.email_normalized}"
                if "mobile" in record:
                    record_info += f"- mobile {record.mobile}"
                if "phone" in record:
                    record_info += f"- phone {record.phone}"
            elif record_unlinked := all_records_unlinked.filtered(lambda r: r.id == trace.res_id):
                record_info = f"-unlinked ID.{record_unlinked.id}"
            traces_info.append(
                f'Trace: doc {trace.res_id} - activity {trace.activity_id.id} ({trace.activity_id.activity_type}) - status {trace.state}'
                f' - rec: {record_info}'
            )
        debug_info = '\n'.join(traces_info)

        # check traces / records coherency through campaign
        canceled_res_ids = canceled_res_ids or set()
        all_record_ids = set(all_records.ids) | set(all_records_unlinked.ids) | canceled_res_ids
        if strict:
            additional = set(traces.mapped('res_id')) - all_record_ids
            missing = all_record_ids - set(traces.mapped('res_id'))
            self.assertEqual(
                set(traces.mapped('res_id')), all_record_ids,
                f'Should find one trace / record. Missing traces {missing} - Unexpected traces {additional}. Found\n{debug_info}'
            )
            self.assertEqual(
                len(traces), len(all_records) + len(all_records_unlinked) + len(canceled_res_ids),
                f'Should find one trace / record. Found\n{debug_info}'
            )
        else:
            self.assertTrue(set(all_record_ids) < set(traces.mapped('res_id')))
        for canceled_res_id in canceled_res_ids:
            linked_trace = traces.filtered(lambda t: t.res_id == canceled_res_id)
            self.assertTrue(linked_trace)
            self.assertEqual(linked_trace.state, 'canceled')

        for info in participants_info:
            # check input
            invalid = set(info.keys()) - {
                # participants
                'participants',
                'participants_state',
                # marketing trace
                'fields_values',
                'quick',
                'status',  # marketing.trace status
                # records
                'records',
                'records_missing',
                # mail
                'check_mail',
                'email_values',
                'mailing_trace_values',
                'mail_values',
                'trace_content',
                'trace_email',
                'trace_email_to_mail',
                'trace_email_to_recipients',
                'trace_failure_reason',
                'trace_failure_type',
                'trace_status',  # mailing.trace status
                # sms (see sms modules)
                'check_sms',
                'sms_values',
                'sent_unlink',  # whether sms are unlinked, hence checking IAP mock data directly
                'trace_sms_number',
                # whatsapp (see wa modules)
                'wa_from_mock',
                'wa_msg_values',
                # record-based info
                'records_to_email_to_mail',
                'records_to_email_to_recipients',
                'records_to_trace_email',
                'records_to_trace_status',
                'records_to_number',
                'records_to_partner',
            }
            if invalid:
                raise AssertionError(f"assertMarketAutoTraces: invalid input {invalid}")

            records = info['records']
            linked_traces = traces.filtered(lambda t: t.res_id in records.ids)

            # check link to records, continue if no records (aka no traces)
            if not records:
                self.assertFalse(linked_traces)
                continue
            self.assertEqual(set(linked_traces.mapped('res_id')), set(records.ids))

            # check trace details
            fields_values = info.get('fields_values') or {}
            for trace in linked_traces:
                record = records.filtered(lambda r: r.id == trace.res_id)
                if not info.get('records_missing'):
                    trace_info = f'Trace {trace.id}: doc {trace.res_id} ({record.email_normalized}-{record.name})'
                else:
                    trace_info = f'Trace {trace.id}: doc {trace.res_id} (unlinked record)'

                # asked marketing.trace values
                self.assertEqual(
                    trace.state, info['status'],
                    f"Received {trace.state} instead of {info['status']} for {trace_info}\nDebug\n{debug_info}")
                for fname, fvalue in fields_values.items():
                    with self.subTest(fname=fname, fvalue=fvalue):
                        self.assertEqual(
                            trace[fname], fvalue,
                            f'Marketing Trace: expected {fvalue} for {fname}, got {trace[fname]} for {trace_info}'
                        )

            if info.get('quick'):
                continue

            # check sub-records (mailing related notably)
            if info.get('trace_status') and activity.activity_type == 'mail':
                self.assertMarketAutoTracesMail(info, activity, traces)
            elif not info.get('trace_status'):
                self.assertEqual(linked_traces.mailing_trace_ids, self.env['mailing.trace'])

            # marketing.participant check
            if participants := info.get('participants'):
                self.assertEqual(linked_traces.participant_id, participants)
            if participants_state := info.get('participants_state'):
                self.assertEqual(set(linked_traces.participant_id.mapped('state')), {participants_state})
        return traces

    def assertMarketAutoTracesMail(self, participant_info, activity, traces):
        # prepare optional record-specific values
        partners = participant_info.get('records_to_partner', {})
        trace_emails = participant_info.get('records_to_trace_email', {})
        mail_emails = participant_info.get('records_to_email_to_mail', {})
        email_emails = participant_info.get('records_to_email_to_recipients', {})
        statuses = participant_info.get('records_to_trace_status', {})
        records_add_info = []
        for record in participant_info['records']:
            add_info = {
                'email': trace_emails.get(record.id, participant_info.get('trace_email', record.email_normalized)),
                'partner': partners.get(record.id) or self.env['res.partner'],
                'trace_status': statuses.get(record.id) or participant_info['trace_status'],
            }

            if record.id in mail_emails:
                add_info['email_to_mail'] = mail_emails[record.id]
            elif 'trace_email_to_mail' in participant_info:
                add_info['email_to_mail'] = participant_info['trace_email_to_mail']
            elif not partners.get(record.id):
                add_info['email_to_mail'] = record[record._primary_email] or ''

            if record.id in email_emails:
                add_info['email_to_recipients'] = email_emails[record.id]
            elif 'trace_email_to_recipients' in participant_info:
                add_info['email_to_recipients'] = participant_info['trace_email_to_recipients']
            records_add_info.append(add_info)
        self.assertMailTraces(
            [{
                # record info
                'record': record,
                # trace / mail.mail
                'failure_type': participant_info.get('trace_failure_type', False),
                'failure_reason': participant_info.get('trace_failure_reason', False),
                'trace_values': participant_info.get('mailing_trace_values') or {},
                # mail.mail
                'content': participant_info.get('trace_content'),
                'mail_values': participant_info.get('mail_values'),
                # outgoing email
                'email_values': participant_info.get('email_values'),
                # other precomputed info (email, partner, ...)
                **add_info,
                } for record, add_info in zip(participant_info['records'], records_add_info)
            ],
            activity.mass_mailing_id,
            participant_info['records'],
            check_mail=participant_info.get('check_mail', True),
        )

    def assertActivityProcessed(self, activities, records, sd=None):
        """ Quick assert """
        return self._assertActivityStatus(activities, records, 'processed', sd=sd)

    def assertActivityScheduled(self, activities, records, sd=None):
        """ Quick assert """
        return self._assertActivityStatus(activities, records, 'scheduled', sd=sd)

    def assertActivityWaiting(self, activities, records, sd=None):
        """ Quick assert """
        return self._assertActivityStatus(activities, records, 'waiting', sd=sd)

    def _assertActivityStatus(self, activities, records, status, sd=None):
        """ Quick assert, hiding a few stuff hence to use only when caring about
        global details. """
        for activity in activities:
            if status == 'processed':
                traces = self.env['marketing.trace'].search([
                    ('activity_id', 'in', activity.ids),
                ])
                self.assertEqual(len(traces), len(records))
                states = set(traces.mapped('state'))
                self.assertFalse(states & {'scheduled', 'rejected'})
                continue

            fields_values = {}
            if sd is not None:
                fields_values['schedule_date'] = sd
            assert_values = {
                'check_mail': False,  # too complicated
                'check_sms': False,  # too complicated
                'fields_values': fields_values,
                'records': records,
                'status': status,
            }
            if (activity.activity_type == 'mail' and status == 'processed') or (activity.activity_type == 'sms' and status == 'processed'):
                assert_values['trace_status'] = 'sent'

            with self.subTest(activity_name=activity.name):
                self.assertMarketAutoTraces(
                    [assert_values],
                    activity,
                )

    def assertActivityWoTrace(self, activities):
        """ Ensure activity has no traces linked to it """
        for activity in activities:
            with self.subTest(activity=activity):
                self.assertMarketAutoTraces([{'records': self.env[activity.model_name]}], activity)

    # ------------------------------------------------------------
    # CRON TOOLS AND ASSERTS
    # ------------------------------------------------------------

    def _assert_cron_progress(self, cron, count, done=0, remaining=0, deactivate=False, timed_out_counter=0):
        progresses = self.env['ir.cron.progress'].search([('cron_id', '=', cron.id)], order='id DESC')
        self.assertEqual(len(progresses), count)
        if count:
            self.assertEqual(progresses[0].deactivate, deactivate)
            self.assertEqual(progresses[0].done, done)
            self.assertEqual(progresses[0].remaining, remaining)
            self.assertEqual(progresses[0].timed_out_counter, timed_out_counter)

    def _assert_cron_state(self, cron, **fields_values):
        fields_values.setdefault('active', True)
        fields_values.setdefault('failure_count', 0)
        fields_values.setdefault('first_failure_date', False)
        for fname, fvalue in fields_values.items():
            self.assertEqual(cron[fname], fvalue,
                             f'Cron {cron.name} invalid value for {fname}: expected {fvalue}, got {cron[fname]}')

    # ------------------------------------------------------------
    # RECORDS TOOLS
    # ------------------------------------------------------------

    @classmethod
    def _create_mailing(cls, model, user=None, **mailing_values):
        mailing_type = mailing_values.get("mailing_type", "mail")
        vals = {
            'body_html': """<div><p>Hello {{ object.name }}<br/>You rock</p>
<p>click here <a id="url0" href="https://www.example.com/foo/bar?baz=qux">LINK</a></p>
</div>""",
            'mailing_model_id': cls.env['ir.model']._get_id(model),
            'mailing_type': mailing_type,
            'preview': 'Hi {{ object.name }} :)',
            'reply_to_mode': 'update',
            'subject': 'Test for {{ object.name }}',
            'use_in_marketing_automation': True,
        }
        if mailing_type == 'mail':
            vals['body_html'] = """<div><p>Hello {{ object.name }}<br/>You rock</p>
<p>click here <a id="url0" href="https://www.example.com/foo/bar?baz=qux">LINK</a></p>
</div>"""
        else:
            vals['body_plaintext'] = "Test SMS for {{ object.name }} click on https://www.example.com/foo/bar?baz=qux"

        if user:
            vals['email_from'] = user.email_formatted
            vals['user_id'] = user.id
        vals.update(**mailing_values)
        return cls.env['mailing.mailing'].create(vals)

    @classmethod
    def _create_server_action(cls, model, code, **sa_values):
        vals = {
            "code": code,
            "model_id": cls.env["ir.model"]._get_id(model),
            "name": "Test SA",
            "state": "code",
        }
        vals.update(**sa_values)
        return cls.env['ir.actions.server'].create(vals)

    @classmethod
    def _create_activity(cls, campaign, mailing=None, wa_template=None, action=None, **act_values):
        vals = {}
        if mailing:
            if mailing.mailing_type == 'mail':
                vals.update({
                    'mass_mailing_id': mailing.id,
                    'activity_type': 'mail',
                })
            else:
                vals.update({
                    'mass_mailing_id': mailing.id,
                    'activity_type': 'sms',
                })
        elif wa_template:
            vals.update({
                'activity_type': 'whatsapp',
                'whatsapp_template_id': wa_template.id,
            })
        elif action:
            vals.update({
                'server_action_id': action.id,
                'activity_type': 'action',
            })
        vals.update({
            'campaign_id': campaign.id,
        })
        vals.update(**act_values)
        if act_values.get('create_date'):
            with cls.mock_datetime_and_now(act_values['create_date']):
                activity = cls.env['marketing.activity'].create(vals)
        else:
            activity = cls.env['marketing.activity'].create(vals)
        return activity

    @classmethod
    def _create_activity_log_note(cls, campaign, log_note_body=None, act_values=None):
        act_values = act_values or {}
        act_values['activity_type'] = 'log_note'
        act_values['log_note_body'] = log_note_body or '<p>Test Log Note</p>'
        return cls._create_activity(campaign, **act_values)

    @classmethod
    def _create_activity_mail(cls, campaign, user=None, mailing_values=None, act_values=None):
        mailing_values = {**(mailing_values or {}), 'campaign_id': campaign.utm_campaign_id.id}
        new_mailing = cls._create_mailing(campaign.model_name, user=user, **mailing_values)
        return cls._create_activity(campaign, mailing=new_mailing, **(act_values or {}))

    @classmethod
    def _create_activity_sa(cls, campaign, code, sa_values=None, act_values=None):
        new_sa = cls._create_server_action(campaign.model_name, code, **(sa_values or {}))
        return cls._create_activity(campaign, action=new_sa, **(act_values or {}))

    @classmethod
    def _create_activity_split(cls, campaign, split_domain, act_values=None):
        act_values = act_values or {}
        act_values['activity_type'] = 'split'
        act_values['split_domain'] = split_domain
        return cls._create_activity(campaign, **act_values)

    @classmethod
    def _create_activity_subscribe(cls, campaign, mailing_list, action='add', act_values=None):
        act_values = act_values or {}
        act_values['activity_type'] = 'subscribe_to_list'
        act_values['subscribe_to_list_id'] = mailing_list.id
        act_values['subscribe_to_list_action'] = action
        return cls._create_activity(campaign, **act_values)

    @classmethod
    def _create_activity_wa(cls, campaign, user=None, template_values=None, act_values=None):
        new_wa_template = cls._create_wa_template(campaign.model_name, user=user, **(template_values or {}))
        return cls._create_activity(campaign, wa_template=new_wa_template, **(act_values or {}))

    def _force_activity_create_date(self, activities, create_date):
        """ As create_date is set through sql NOW it is not possible to mock
        it easily. """
        self.env.cr.execute(
            "UPDATE marketing_activity SET create_date=%s WHERE id IN %s",
            (create_date, tuple(activities.ids),)
        )

    def _launch_campaign(self, campaign, date_reference=None):
        with self.mock_datetime_and_now(date_reference or fields.Datetime.now()):
            campaign.action_start_campaign()
            campaign._synchronize_participants()


class MarketingAutomationCommon(MarketingAutomationCase, MassMailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_marketing_automation = mail_new_test_user(
            cls.env,
            email='user.marketing.automation@test.example.com',
            groups='base.group_user_regular,base.group_partner_manager,marketing_automation.group_marketing_automation_user',
            login='user_marketing_automation',
            name='Mounhir MarketAutoUser',
            signature='--\nM'
        )

        cls.test_countries = [
            cls.env['res.country'],
            cls.env.ref('base.be'),
            cls.env.ref('base.in'),
            cls.env.ref('base.us'),
            cls.env.ref('base.fr'),
        ]
        cls.test_contacts = cls.env['mailing.contact'].create([
            {
                'country_id': cls.test_countries[idx % len(cls.test_countries)].id,
                'email': f'ma.test.contact.{idx}@example.com',
                'name': f'MATest_{idx:02d}',
            }
            for idx in range(10)
        ])
        cls.campaign = cls.env['marketing.campaign'].create({
            'enroll_domain': [('name', 'like', 'MATest')],
            'model_id': cls.env['ir.model']._get_id('mailing.contact'),
            'name': 'Test Campaign',
            'title': 'Test Campaign',
            'user_id': cls.user_marketing_automation.id,
        })

        # ensure batch size for generation to have deterministic tests and check iterative behavior
        cls.env["ir.config_parameter"].sudo().set_int("mail.batch_size", 50)
        cls.env["ir.config_parameter"].sudo().set_int("marketing.execute.batch.size", 100)  # trace execution
        cls.env["ir.config_parameter"].sudo().set_int("marketing.trace.batch.size", 50)  # trace generation
