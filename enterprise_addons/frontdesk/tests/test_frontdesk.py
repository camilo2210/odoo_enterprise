# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.addons.mail.tests.common import MailCase


class TestFrontDesk(MailCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Test Company', 'email': 'your.company@example.com'})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.partner_1, cls.partner_2 = cls.env['res.partner'].create([{
            'name': 'Test Partner 1',
            'email': 'test1@example.com',
        }, {
            'name': 'Test Partner 2',
            'email': 'test2@example.com',
        }])
        cls.user_1, cls.user_2 = cls.env['res.users'].create([{
            'name': 'Test User 1',
            'login': 'test_user_1',
            'partner_id': cls.partner_1.id,
        }, {
            'name': 'Test User 2',
            'login': 'test_user_2',
            'partner_id': cls.partner_2.id,
        }])
        cls.employee_1, cls.employee_2, cls.employee_3 = cls.env['hr.employee'].create([{
            'name': 'Host 1',
            'user_id': cls.user_1.id,
            'work_phone': '1234567890',
            'work_email': 'test_work1@example.com',
        }, {
            'name': 'Host 2',
            'user_id': cls.user_2.id,
            'work_phone': '0987654321',
            'work_email': 'test_work2@example.com',
        }, {
            'name': 'Host 3',
            'work_email': False,
            'work_phone': False,
        }])
        cls.station = cls.env['frontdesk.frontdesk'].create({
            'name': 'office_1',
            'host_selection': True,
            'ask_email': True,
            'ask_phone': True,
            'company_id': cls.company.id,
        })

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def assert_discuss_notification(self, user_name):
        channel = self.env['discuss.channel'].search_count(['&', ('name', 'ilike', 'OdooBot'), ('name', 'ilike', user_name)])
        self.assertEqual(channel, 1)

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------
    def test_host_notify_discuss(self):
        '''Test that a host with a linked user gets the notification through Discuss when a visitor checks in'''

        self.station.notify_discuss = True
        host_name = self.employee_1.user_id.name
        self.env['frontdesk.visitor'].create({
            'name': 'Visitor_1',
            'station_id': self.station.id,
            'host_id': self.employee_1.id,
        })
        self.assert_discuss_notification(host_name)

    def test_host_with_no_user_email_fallback(self):
        '''Test that host without user, notify fallback to email instead of discuss even if notify_email is False'''

        host = self.env['hr.employee'].create({
            'name': 'Host with Email',
            'work_email': 'host_email@example.com',
        })
        self.station.notify_discuss = True
        self.station.notify_email = False
        with self.mock_mail_gateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_4',
                'station_id': self.station.id,
                'host_id': host.id,
            })
        self.assertSentEmail('"OdooBot" <odoobot@example.com>', ['"Host with Email" <host_email@example.com>'])

    def test_host_with_all_notify_true_send_email(self):
        '''If all notify settings are enabled, host without user_id but with email and gets email posted to visitor chatter.'''

        host = self.env['hr.employee'].create({
            'name': 'Host All Channels',
            'work_email': 'host_all@example.com',
            'work_phone': '5551112222',
        })
        self.station.notify_discuss = True
        self.station.notify_email = True
        with self.mock_mail_gateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_7',
                'station_id': self.station.id,
                'host_id': host.id,
            })
        self.assertSentEmail('"OdooBot" <odoobot@example.com>', ['"Host All Channels" <host_all@example.com>'])

    def test_host_notify_mail(self):
        '''Test that the host gets the notification through email when visitor checks in'''

        self.station.notify_email = True
        with self.mock_mail_gateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_1',
                'station_id': self.station.id,
                'host_id': self.employee_1.id,
            })
        self.assertSentEmail('"OdooBot" <odoobot@example.com>', self.partner_1)

    def test_responsible_notify_discuss(self):
        ''' Test that the station responsible person gets the notification on
        discuss when visitor checks in'''

        self.station.write({
            'responsible_ids': [(4, self.user_1.id)],
        })
        responsible_name = self.station.responsible_ids.name
        self.env['frontdesk.visitor'].create({
            'name': 'Visitor_1',
            'station_id': self.station.id,
            'host_id': self.employee_1.id,
        })
        self.assert_discuss_notification(responsible_name)

    def test_check_and_notify_visitor_host_on_leave(self):
        '''Test that when a visitor's host is on leave, the visitor is notified via email'''

        check_in_time = datetime.now()
        self.env['resource.calendar.leaves'].create({
            'name': 'Host Leave',
            'date_from': check_in_time - timedelta(hours=1),
            'date_to': check_in_time + timedelta(hours=1),
            'resource_id': self.employee_1.resource_id.id,
            'calendar_id': self.env.company.resource_calendar_id.id,
            'count_as': 'absence',
        })

        visitor_data = {
            'name': 'Visitor_Notify_1',
            'email': 'visitornotify@example.com',
            'phone': '1234567890',
            'station_id': self.station.id,
            'host_id': self.employee_1.id,
            'check_in': check_in_time,
        }

        with self.mock_mail_gateway():
            visitor1 = self.env['frontdesk.visitor'].create(visitor_data)

        visitor_messages = visitor1.message_ids.filtered(lambda m: m.message_type == 'comment')
        self.assertEqual(len(visitor_messages), 1, "Visitor should receive 1 email")

    def test_constraint_with_invalid_hosts(self):
        '''The constraint triggers when any selected host is missing required contact info.'''

        with self.assertRaises(ValidationError):
            self.station.write({
                'notify_email': True,
                'host_ids': [
                    Command.link(self.employee_3.id),
                ],
            })

    def test_cron_auto_checkout(self):
        """Test that the cron mass-checks-out visitors whose auto_checkout_time has passed."""
        self.station.auto_checkout_hours = 1
        visitor_expired = self.env["frontdesk.visitor"].create(
            {
                "name": "Visitor_Expired",
                "station_id": self.station.id,
                "host_id": self.employee_1.id,
                "check_in": datetime.now() - timedelta(hours=2),
            }
        )
        visitor_recent = self.env["frontdesk.visitor"].create(
            {
                "name": "Visitor_Recent",
                "station_id": self.station.id,
                "host_id": self.employee_2.id,
                "check_in": datetime.now(),
            }
        )
        self.assertEqual(
            visitor_expired.state,
            "checked_in",
            "Visitor state should be 'checked_in' before cron execution.",
        )
        self.assertEqual(
            visitor_recent.state,
            "checked_in",
            "Visitor state should be 'checked_in' before cron execution.",
        )
        with self.enter_registry_test_mode():
            self.env.ref("frontdesk.cron_auto_checkout_visitors").method_direct_trigger()
        self.assertEqual(
            visitor_expired.state,
            "checked_out",
            "Visitor should be auto-checked-out after auto_checkout_time has passed.",
        )
        self.assertTrue(visitor_expired.check_out, "check_out datetime should be set.")
        self.assertEqual(
            visitor_recent.state,
            "checked_in",
            "Recent visitor should remain checked-in.",
        )

    def test_no_email_when_frontdesk_has_no_mail_template(self):
        """Ensure no email is sent when the Frontdesk has no mail template configured."""
        self.employee_1.user_id = False
        self.station.mail_template_id = False

        self.assertFalse(self.station.notify_email)

        with self.mock_mail_gateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Test Visitor',
                'station_id': self.station.id,
                'host_id': self.employee_1.id,
            })

        self.assertEqual(self._mails, [])


class TestKioskUrlGeneration(TransactionCase):

    def test_kiosk_url_generation(self):
        # Dynamically check if the website module is installed
        Website = self.env['ir.module.module'].sudo().search([('name', '=', 'website')])
        if not Website or Website.state != 'installed':
            self.skipTest("The 'website' module is not installed, skipping the test.")

        # Set up the website
        website = self.env['website'].create({
            'name': 'Test Website',
        })

        # Create the frontdesk station
        station = self.env['frontdesk.frontdesk'].create({
            'name': 'test_1',
            'host_selection': True,
        })
        station.company_id.website_id = website
        # Compute the initial URL
        old = station.kiosk_url

        # Update the website domain and recompute the URL
        website.domain = "https://www.test.com"
        station._compute_kiosk_url()
        new = station.kiosk_url

        # Assert that the URL has not changed due to the website domain
        self.assertEqual(old, new, "HR related links should not be changed by the website domain.")
