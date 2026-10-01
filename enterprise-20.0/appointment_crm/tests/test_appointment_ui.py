# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.urls import url_encode

from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import common, tagged


@tagged('appointment_ui', 'post_install', '-at_install')
class AppointmentCrmUITest(AppointmentCommon, MailCommon, common.HttpCase):

    def test_apt_with_lead_anonymous_create_with_multi_company(self):
        """ Test that an anonymous user can create an appointment from the website using information
        from an existing contact that belongs to a different company than the one associated with the
        appointment user, with lead_create enabled. """
        apt = self.apt_type_bxls_2days
        apt.write({
            'lead_create': True,
            'is_published': True,
        })
        apt_user = self.staff_user_bxls
        self.assertFalse(apt.meeting_ids)

        partner = self.partner_employee_c2
        partner.company_id = self.company_2
        date_str = '2022-02-14 12:00:00'
        self.assertNotIn(self.company_2, apt_user.company_ids)
        initial_partner_count = self.env['res.partner'].search_count([('email', '=', partner.email)])

        apt_submit_url = f"/appointment/{apt.id}/submit?" + url_encode({
            'staff_user_id': apt_user.id,
            'date_time': date_str,
            'duration': 1,
        })

        self.authenticate(None, None)
        phone_question = apt._get_main_phone_question()
        self.assertTrue(phone_question)
        data = {
            "allday": 0,
            "csrf_token": self.csrf_token(),
            "datetime_str": date_str,
            "duration_str": "1.0",
            "name": "12345",
            "email": partner.email,
            f"question_{phone_question.id}": "12345"
        }
        response = self.url_open(apt_submit_url, data=data)
        self.assertEqual(response.status_code, 200)

        new_partner_count = self.env['res.partner'].search_count([('email', '=', partner.email)])
        self.assertEqual(new_partner_count, initial_partner_count + 1, "Expected one additional partner with the same email.")

        self.assertEqual(len(apt.meeting_ids), 1)
        lead = apt.meeting_ids.opportunity_id
        self.assertTrue(lead, "A lead should have been created with the meeting")
        self.assertTrue(lead.partner_id != partner and lead.partner_id.email == partner.email)
        attendee_partners = apt.meeting_ids.attendee_ids.mapped("partner_id")
        self.assertTrue(len(attendee_partners) == 2 and lead.partner_id in attendee_partners)
