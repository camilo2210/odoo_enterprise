# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from freezegun import freeze_time

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class AppointmentHrRecruitmentTest(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.job = cls.env['hr.job'].create({
            'name': 'Test Job',
            'no_of_recruitment': 1,
        })
        cls.stage_new, cls.stage_qualification, cls.stage_hired = cls.env['hr.recruitment.stage'].create([
            {
                'name': 'New',
                'sequence': 0,
                'hired_stage': False,
            },
            {
                'name': 'Qualification',
                'sequence': 0,
                'hired_stage': False,
                'template_id': cls.env.ref(
                    'appointment_hr_recruitment.email_template_data_applicant_schedule_interview'
                ).id
            },
            {
                'name': 'Hired',
                'sequence': 1,
                'hired_stage': True,
            }
        ])
        cls.test_applicant = cls.env['hr.applicant'].create({
            'partner_name': 'Test Applicant',
            'email_from': 'test@applicant.com',
            'job_id': cls.job.id,
            'stage_id': cls.stage_new.id
        })
        cls.appointment = cls.env['appointment.type'].create({
            'appointment_tz': 'UTC',
            'is_auto_assign': True,
            'min_schedule_hours': 1.0,
            'max_schedule_days': 8,
            'name': 'Test',
            'appointment_invite_ids': [
                Command.create({
                    'short_code': "short-test-code"
                })
            ]
        })

    @freeze_time("2019-10-25 07:00:00")
    def test_archive_meet_applicant_state_change(self):
        """
            If an application is in the archived, refused, or hired stage, all future linked meetings should be archived
            while past linked meetings should remain unaffected
        """
        future_event = self.env["calendar.event"].create({
            'name': "Doom's day",
            'start': datetime(2019, 10, 25, 8, 0),
            'stop': datetime(2019, 10, 27, 18, 0),
            'applicant_id': self.test_applicant.id,
        })
        past_event = self.env["calendar.event"].create({
            'name': "Doom's day",
            'start': datetime(2019, 10, 22, 11, 0),
            'stop': datetime(2019, 10, 22, 23, 0),
            'applicant_id': self.test_applicant.id,
        })
        self.test_applicant.action_archive()
        self.assertFalse(future_event.active)
        self.assertTrue(past_event.active)
        self.test_applicant.action_unarchive()
        future_event.write({'active': True})

        refuse_reason = self.env['hr.applicant.refuse.reason'].create([{'name': 'Fired'}])
        applicant_get_refuse_reason = self.env['applicant.get.refuse.reason'].create({
            'refuse_reason_id': refuse_reason.id,
            'applicant_ids': [Command.set(self.test_applicant.ids)]
        })
        applicant_get_refuse_reason.action_refuse_reason_apply()
        self.assertFalse(future_event.active)
        self.assertTrue(past_event.active)
        self.test_applicant.action_unarchive()
        future_event.write({'active': True})

        self.test_applicant.write({'stage_id': self.stage_hired.id})
        self.assertFalse(future_event.active)
        self.assertTrue(past_event.active)
        self.test_applicant.action_unarchive()
        future_event.write({'active': True})

    def test_schedule_meet_link_expiry(self):
        """
            Test that if an application is refused, archived, or contract-signed, the schedule_meet link should not work
            Also, all calendar.event records linked to the application should be archived

            Test Case:
            =========
            1) appointment link accessible case -> link should be accessible
            2) application refused case -> appointment link expired
            3) application archived case -> appointment link expired
            4) hired(contract-signed) stage cases -> appointment link expired
            5) applicant already have an event -> should archived on applicant's archive/refused/contract-signed case
        """
        interview_url = (
            f'{self.appointment.appointment_invite_ids.book_url}'
            f'?applicant_code={self.test_applicant.interview_invite_code}'
        )
        expired_link_template_text = "Interview Link Unavailable"

        # 1) appointment link accessible case -> link should be accessible
        self.test_applicant.write({'stage_id': self.stage_qualification.id})
        self._open_url_match_text(interview_url, expired_link_template_text, contain_text=False)

        # 2) application refused case -> appointment link expired
        refuse_reason = self.env['hr.applicant.refuse.reason'].create([{'name': 'Fired'}])
        applicant_get_refuse_reason = self.env['applicant.get.refuse.reason'].create([{
            'refuse_reason_id': refuse_reason.id,
            'applicant_ids': [Command.link(self.test_applicant.id)],
            'duplicates': True
        }])
        applicant_get_refuse_reason.action_refuse_reason_apply()
        self.test_applicant.action_unarchive()

        # 3) application archived case -> appointment link expired
        self.test_applicant.action_archive()
        self._open_url_match_text(interview_url, expired_link_template_text, contain_text=True)
        self.test_applicant.action_unarchive()

        # 4) hired(contract-signed) stage cases -> appointment link expired
        self.test_applicant.write({'stage_id': self.stage_hired.id})
        self._open_url_match_text(interview_url, expired_link_template_text, contain_text=True)
        self.test_applicant.action_unarchive()

        # 5) applicant already have an event -> should archived on applicant's archive/refused/contract-signed case
        applicant_event = self.env['calendar.event'].create({
            'name': 'Test calender event',
            'applicant_id': self.test_applicant.id
        })
        self.test_applicant.action_archive()
        self.assertEqual(applicant_event.active, False)

    def _open_url_match_text(self, url, text, contain_text=True):
        """
            method to check whether url response contains specific text in `it or not
        """
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        if contain_text:
            self.assertIn(text, res.content.decode('utf-8'))
        else:
            self.assertNotIn(text, res.content.decode('utf-8'))
