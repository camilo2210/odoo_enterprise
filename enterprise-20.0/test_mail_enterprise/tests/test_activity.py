from freezegun import freeze_time
from markupsafe import Markup

from odoo import fields
from odoo.addons.sms.tests.common import SMSCommon
from odoo.addons.test_mail_sms.tests.common import TestSMSRecipients
from odoo.tests.common import HttpCase, users
from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged('mail_activity')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestActivity(SMSCommon, TestSMSRecipients, HttpCase):

    @classmethod
    def setUpClass(cls):
        super(TestActivity, cls).setUpClass()

        cls.test_record_voip = cls.env['mail.test.activity.bl.sms.voip'].create({
            'name': 'Test Record',
            'customer_id': cls.partner_1.id,
            'email_from': cls.partner_1.email,
            'phone_nbr': '0456999999',
        })

        cls.phonecall_activity = cls.env.ref('mail.mail_activity_data_call')
        cls.phonecall_activity.write({
            'default_user_id': cls.user_admin.id,
            'default_note': 'Test Default Note',
            'summary': 'Test Default Summary',
        })

        # clean db to ease tests
        cls.env['mail.activity.type'].search([
            ('category', '=', 'phonecall'),
            ('id', '!=', cls.phonecall_activity.id),
        ]).unlink()

    def test_activity_data(self):
        """ Ensure initial data for tests """
        self.assertEqual(self.partner_1.phone, '0456001122')
        self.assertTrue(self.phonecall_activity)
        self.assertEqual(self.phonecall_activity.category, 'phonecall')

    @users('employee')
    @mute_logger('odoo.addons.voip.models.voip_activity_mixin')
    def test_create_call_activity(self):
        record = self.test_record_voip.with_env(self.env)

        activity = record.create_call_activity()
        self.assertEqual(activity.activity_type_id, self.phonecall_activity)
        self.assertNotIn('phone', record)
        self.assertEqual(activity.phone, record.phone_formatted)
        self.assertEqual(activity.note, Markup('<p>Test Default Note</p>'))
        self.assertEqual(activity.summary, 'Test Default Summary')

        phonecall_activities = self.env['mail.activity'].sudo().with_context(active_test=False).search([
            ('activity_type_id', '=', self.phonecall_activity.id),
        ])
        phonecall_activities.write({'activity_type_id': False})
        phonecall_activities.flush_recordset()
        # it is now protected, but before protection it was possible to have removed
        # 'Call' activity type (aka you can't do self.phonecall_activity.unlink()
        # but you may have already removed it)
        self.env.cr.execute("DELETE FROM mail_activity_type WHERE id IN %s", (tuple(self.phonecall_activity.ids),))
        self.env['ir.model.data'].sudo().search([('name', '=', 'mail_activity_data_call'), ('module', '=', 'mail')]).unlink()

        # no more phonecall activity -> will be dynamically created
        self.assertFalse(self.env['mail.activity.type'].search([('category', '=', 'phonecall')]))
        activity = record.create_call_activity()
        new_activity_type = self.env['mail.activity.type'].search([('category', '=', 'phonecall')])
        self.assertTrue(bool(new_activity_type))

    @users('employee')
    def test_type_phonecall(self):
        # Set delay_count to 0 to schedule activity today as date_deadline is now computed based on delay_count.
        self.phonecall_activity.write({'delay_count': 0})
        activities = self.env['mail.activity'].create([
            {
                'activity_type_id': self.phonecall_activity.id,
                'phone': '+32455001122',
                'user_id': self.user_employee.id,
            },
            {
                'activity_type_id': self.phonecall_activity.id,
                'phone': '+32455334455',
                'user_id': self.user_employee.id,
            },
        ])
        stored_free = self.env['mail.activity'].get_today_call_activities()._build_result().get('mail.activity')
        self.assertEqual(len(stored_free), len(activities), 'Should have one entry / activity')

    @users('employee')
    @mute_logger('odoo.addons.voip.models.voip_activity_mixin')
    def test_voip_action_done_batch_with_recordings(self):
        """
        Batch test for _action_done covering:
        - Multiple phonecall activities across different models with linked voip calls
        - Mixed phonecall / non-phonecall activities (non-phonecall should not interfere)
        - Correct 1-to-1 message-to-activity pairing
        - Body rendering without recording icon initially
        - upload_recording re-renders only the targeted call's message body with recording icon
        - Calls without recordings remain unchanged
        """
        record_a = self.test_record_voip.with_env(self.env)
        record_b = self.test_record_voip.with_env(self.env).copy()

        activity_a = record_a.create_call_activity()
        activity_b = record_b.create_call_activity()

        call_a = self.env['voip.call'].sudo().create({
            'phone_number': record_a.phone_nbr,
            'activity_id': activity_a.id,
            'is_production': False,
        })
        call_b = self.env['voip.call'].sudo().create({
            'phone_number': record_b.phone_nbr,
            'activity_id': activity_b.id,
            'is_production': False,
        })

        # Phonecall activity on a different model (mail.test.lead)
        # to exercise cross-model ordering in _classify_by_model.
        record_c = self.env['mail.test.lead'].with_env(self.env).create({
            'name': 'Lead C',
            'phone': '0456001122',
        })
        activity_c = self.env["mail.activity"].create({
            "activity_type_id": self.phonecall_activity.id,
            "res_model_id": self.env["ir.model"]._get_id("mail.test.lead"),
            "res_id": record_c.id,
            "user_id": self.env.uid,
            "date_deadline": fields.Date.today(),
        })
        call_c = self.env['voip.call'].sudo().create({
            'phone_number': record_c.phone,
            'activity_id': activity_c.id,
            'is_production': False,
        })

        # Non-phonecall activity to mix ordering (should not get a call link)
        other_record = self.env['mail.test.lead'].with_env(self.env).create({
            'name': 'Other Lead',
            'phone': '0456001122',
        })
        activity_other = other_record.activity_schedule(
            activity_type_id=self.env.ref('mail.mail_activity_data_meeting').id,
            summary='Mixed batch test',
            note='Just a meeting to mix things up',
        )

        # Phase 1: batch _action_done — verify message creation, linking and full body
        self.assertFalse(call_a.activity_mail_message_id)
        self.assertFalse(call_b.activity_mail_message_id)
        self.assertFalse(call_c.activity_mail_message_id)

        with self.mock_mail_gateway(), self.mock_mail_app():
            activities = activity_a | activity_b | activity_c | activity_other
            activities._action_done()

        # All phonecall calls should now be linked to a message
        self.assertTrue(call_a.activity_mail_message_id)
        self.assertTrue(call_b.activity_mail_message_id)
        self.assertTrue(call_c.activity_mail_message_id)

        # Verify each message is associated with the correct record
        self.assertEqual(call_a.activity_mail_message_id.res_id, record_a.id)
        self.assertEqual(call_b.activity_mail_message_id.res_id, record_b.id)
        self.assertEqual(call_c.activity_mail_message_id.res_id, record_c.id)

        # Verify each message's fields and full body (no recording, no feedback)
        self.assertEqual(len(self._new_msgs), 4)
        for msg, call, record in zip(self._new_msgs[:3], (call_a, call_b, call_c), (record_a, record_b, record_c)):
            self.assertTrue(call.activity_mail_message_id)
            self.assertMessageFields(msg, {
                'author_id': self.env.user.partner_id,
                'body': f'''<div>
    <p class="o_mail_activity_title mb-1">
        <span class="oi oi-fw oi-filled" data-icon="phone"></span>
                    <a href="#" class="o_label_info text-primary fw-bold" data-oe-model="voip.call" data-oe-id="{call.id}">
                        Call done (0s)
                    </a>
                    <span> - Test Default Summary</span>
    </p>
    <div class="o_mail_activity_note pb-2">
        <div class="fst-italic">{self.phonecall_activity.default_note}</div>
    </div>
</div>''',
                'mail_activity_type_id': self.phonecall_activity,
                'message_type': 'notification',
                'model': record._name,
                'res_id': record.id,
                'subtype_id': self.env.ref('mail.mt_activities'),
            })

        # Save original bodies for later comparison
        body_a, body_c = call_a.activity_mail_message_id.body, call_c.activity_mail_message_id.body

        # Phase 2: upload a recording for call_b only — verify selective body update
        self.authenticate(self.env.user.login, self.env.user.login)
        frozen_datetime = "2026-05-28 12:38:55"
        with freeze_time(frozen_datetime):
            self.url_open(
                f"/voip/upload_recording/{call_b.id}",
                data={"csrf_token": self.csrf_token(), "start_ms": 0, "end_ms": 5000},
                files={"ufile": ("recording.ogg", b"OggS", "audio/ogg")},
                method="POST",
            )

        call_b.invalidate_recordset(["has_recording", "activity_mail_message_id"])
        self.assertTrue(call_b.has_recording, "call_b should now have a recording")

        # call_b's message body should be updated with recording icon and edited timestamp
        self.assertMessageFields(call_b.activity_mail_message_id, {
            'body': f'''<div>
     <p class="o_mail_activity_title mb-1">
        <span class="oi oi-fw oi-filled" data-icon="phone"></span>
                    <a href="#" class="o_label_info text-primary fw-bold" data-oe-model="voip.call" data-oe-id="{call_b.id}">
                        Call done (0s)
                    </a>
                    <span> - Test Default Summary</span>
                        <i class="oi ms-1 text-muted" data-icon="graphic_eq" aria-hidden="true"></i>
                        <span class="visually-hidden">Recording available</span>
    </p>
    <div class="o_mail_activity_note pb-2">
        <div class="fst-italic">{self.phonecall_activity.default_note}</div>
    </div>
<span class="o-mail-Message-edited" data-o-datetime="{frozen_datetime}"></span></div>''',
        })

        # Other calls should remain unchanged (same body as before)
        for call, original_body in ((call_a, body_a), (call_c, body_c)):
            self.assertEqual(call.activity_mail_message_id.body, original_body)
