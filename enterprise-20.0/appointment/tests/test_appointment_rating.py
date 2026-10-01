from datetime import datetime, timedelta

from odoo import fields
from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user
from odoo.tests import tagged


@tagged('at_install', '-post_install')
class TestAppointmentRating(AppointmentCommon, MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar_event_model_id = cls.env['ir.model']._get_id('calendar.event')

        cls.doctor_user = mail_new_test_user(
            cls.env,
            name='Dr. John Doe',
            login='dr_john_doe',
            email='john_doe@appointment-test.com',
            groups='base.group_user',
        )
        cls.doctor_partner = cls.doctor_user.partner_id

        cls.booker_partner = cls.env['res.partner'].create({
            'name': 'Test Booker',
            'email': 'booker@test.example.com',
        })

        cls.template_a, cls.template_b = cls.env['mail.template'].create([
            {
                'name': f'Feedback Template {letter}',
                'model_id': cls.calendar_event_model_id,
                'subject': f'How was your visit {letter}?',
                'body_html': f'<p>Please rate your visit {letter}</p>',
                'partner_to': '{{ object.appointment_booker_id.id }}',
            }
            for letter in ('A', 'B')
        ])

        cls.type_a, cls.type_b = cls.env['appointment.type'].create([
            {
                'name': f'Appointment Type {letter}',
                'feedback_mail_template_id': template.id,
            }
            for letter, template in zip(('A', 'B'), (cls.template_a, cls.template_b))
        ])

    def test_appointment_feedback_and_rating_workflow(self):
        appointment = self.env['calendar.event'].create({
            'name': 'Specialist Consultation',
            'start': fields.Datetime.now() - timedelta(hours=2),
            'stop': fields.Datetime.now() - timedelta(hours=1),
            'user_id': self.doctor_user.id,
            'appointment_type_id': self.type_a.id,
        })

        rating_val = self.env['rating.rating'].create({
            'res_model_id': self.calendar_event_model_id,
            'res_id': appointment.id,
            'partner_id': self.env.user.partner_id.id,
            'rated_partner_id': self.doctor_partner.id,
        })

        appointment.rating_apply(
            rate=5,
            feedback='The doctor was exceptional!',
            token=rating_val.access_token,
        )

        rating_val.invalidate_recordset()

        self.assertEqual(rating_val.rating, 5)
        self.assertEqual(rating_val.rated_partner_id, self.doctor_partner)
        self.assertEqual(rating_val.parent_res_model, 'appointment.type')
        self.assertEqual(rating_val.parent_res_id, self.type_a.id)

        chatter_messages = self.env['mail.message'].search([
            ('model', '=', 'calendar.event'),
            ('res_id', '=', appointment.id),
        ])
        self.assertTrue(
            any('The doctor was exceptional!' in (msg.body or '') for msg in chatter_messages)
        )

    def test_cron_send_feedback_emails_multi_template(self):
        base_time = datetime(2026, 8, 28, 10, 0, 0)

        with self.mock_datetime_and_now(base_time):
            past_start_time = base_time - timedelta(hours=2)
            past_stop_time = base_time - timedelta(hours=1)

            event_a, event_b = self.env['calendar.event'].create([
                {
                    'name': f'Visit {letter}',
                    'appointment_type_id': appt_type.id,
                    'appointment_status': 'booked',
                    'start': past_start_time,
                    'stop': past_stop_time,
                    'appointment_booker_id': self.booker_partner.id,
                }
                for letter, appt_type in (('A', self.type_a), ('B', self.type_b))
            ])

            event_ignored_status = self.env['calendar.event'].create({
                'name': 'Missed Visit',
                'appointment_type_id': self.type_a.id,
                'appointment_status': 'booked',
                'start': past_start_time,
                'stop': past_stop_time,
                'appointment_booker_id': self.booker_partner.id,
            })

        valid_events = event_a | event_b
        self.assertFalse(any(valid_events.mapped('require_appointment_feedback_mail')))
        self.assertFalse(event_ignored_status.require_appointment_feedback_mail)

        valid_events.write({'appointment_status': 'attended'})
        event_ignored_status.write({'appointment_status': 'no_show'})
        self.assertTrue(all(valid_events.mapped('require_appointment_feedback_mail')))
        self.assertFalse(event_ignored_status.require_appointment_feedback_mail)

        cron_execution_time = base_time + timedelta(days=2)
        with self.mock_datetime_and_now(cron_execution_time):
            event_too_recent = self.env['calendar.event'].create({
                'name': 'Recent Visit',
                'appointment_type_id': self.type_a.id,
                'appointment_status': 'booked',
                'start': cron_execution_time - timedelta(hours=2),
                'stop': cron_execution_time - timedelta(hours=1),
                'appointment_booker_id': self.booker_partner.id,
            })
            event_too_recent.write({'appointment_status': 'attended'})

            with self.mock_mail_gateway(), self.mock_mail_app():
                self.env.ref('appointment.ir_cron_appointment_send_feedback_emails').method_direct_trigger()

        self.assertEqual(len(self._new_msgs), 2)
        for event, letter in ((event_a, 'A'), (event_b, 'B')):
            event_msg = self._new_msgs.filtered(lambda m: m.model == 'calendar.event' and m.res_id == event.id)
            self.assertEqual(len(event_msg), 1)
            self.assertMessageFields(
                event_msg,
                {
                    'subject': f'How was your visit {letter}?',
                    'body_content': f'Please rate your visit {letter}',
                    'subtype_id': self.env.ref('mail.mt_note'),
                    'notification_ids': self.env['mail.notification'],
                }
            )

        self.assertFalse(any(valid_events.mapped('require_appointment_feedback_mail')))
        self.assertFalse(event_ignored_status.require_appointment_feedback_mail)
        self.assertTrue(event_too_recent.require_appointment_feedback_mail)
