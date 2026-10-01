# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.addons.sms.tests.common import SMSCase


class TestFrontdeskSms(SMSCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.company = cls.env['res.company'].create({
            'name': 'SMS Test Company',
            'email': 'sms.company@example.com',
        })
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.partner_1 = cls.env['res.partner'].create({
            'name': 'SMS Test Partner 1',
            'email': 'smstest1@example.com',
        })
        cls.user_1 = cls.env['res.users'].create({
            'name': 'SMS Test User 1',
            'login': 'sms_test_user_1',
            'partner_id': cls.partner_1.id,
        })
        cls.employee_1, cls.employee_3 = cls.env['hr.employee'].create([{
            'name': 'SMS Host 1',
            'user_id': cls.user_1.id,
            'work_phone': '9876543210',
            'work_email': 'host@example.com',
            'company_id': cls.company.id,
        }, {
            'name': 'SMS Host 3',
            'work_email': False,
            'work_phone': False,
            'company_id': cls.company.id,
        }])
        sms_template = cls.env.ref('frontdesk_sms.frontdesk_sms_template', raise_if_not_found=False)
        cls.station = cls.env['frontdesk.frontdesk'].create({
            'name': 'SMS Notify Test Station',
            'responsible_ids': [(4, cls.admin.id)],
            'notify_sms': True,
            'ask_phone': True,
            'ask_email': True,
            'host_selection': True,
            'company_id': cls.company.id,
            'sms_template_id': sms_template.id if sms_template else False,
        })
        cls.station.host_ids = [(4, cls.employee_1.id)]

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------
    def test_host_with_no_user_sms_fallback(self):
        '''Test that host without user, notify fallback to sms instead of discuss even if notify_sms is False'''
        host = self.env['hr.employee'].create({
            'name': 'Host with SMS',
            'work_phone': '7778889999',
        })
        self.station.notify_discuss = True
        self.station.notify_email = False
        self.station.notify_sms = False
        with self.mockSMSGateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_5',
                'station_id': self.station.id,
                'host_id': host.id,
            })
        partner_id = host.work_contact_id.id
        sms_count = self.env['sms.sms'].search_count([('partner_id', '=', partner_id)])
        self.assertEqual(sms_count, 1, "Exactly one SMS message should be sent to the host's partner.")

    def test_host_notify_sms(self):
        '''Test that the host gets the notification through SMS when visitor checks in'''
        self.station.notify_sms = True
        with self.mockSMSGateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_1',
                'station_id': self.station.id,
                'host_id': self.employee_1.id,
            })
        sms = self.env['sms.sms'].search_count([('partner_id', '=', self.employee_1.user_id.partner_id.id)])
        self.assertEqual(sms, 1)

    def test_host_with_all_notify_true_send_sms(self):
        '''If all notify settings are enabled, host without user_id but with phone gets SMS'''
        host = self.env['hr.employee'].create({
            'name': 'Host All Channels',
            'work_email': 'host_all@example.com',
            'work_phone': '5551112222',
            'company_id': self.company.id,
        })
        self.station.notify_discuss = True
        self.station.notify_email = True
        self.station.notify_sms = True
        with self.mockSMSGateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_7',
                'station_id': self.station.id,
                'host_id': host.id,
            })
        partner_id = host.work_contact_id.id
        sms_count = self.env['sms.sms'].search_count([('partner_id', '=', partner_id)])
        self.assertEqual(sms_count, 1, "Exactly one SMS should be sent to the host's partner.")

    def test_constraint_with_invalid_hosts_sms(self):
        '''The SMS constraint triggers when host is missing phone number'''
        with self.assertRaises(ValidationError):
            self.station.write({
                'notify_sms': True,
                'host_ids': [Command.link(self.employee_3.id)],
            })

    def test_check_and_notify_visitor_host_on_leave_sms(self):
        '''Test that when host is on leave, visitor is notified via SMS'''
        check_in_time = datetime.now()
        self.env['resource.calendar.leaves'].create({
            'name': 'Host Leave',
            'date_from': check_in_time - timedelta(hours=1),
            'date_to': check_in_time + timedelta(hours=1),
            'resource_id': self.employee_1.resource_id.id,
            'calendar_id': self.env.company.resource_calendar_id.id,
            'count_as': 'absence',
        })
        self.station.notify_sms = False
        visitor_data = {
            'name': 'Visitor_Notify_SMS',
            'email': 'visitornotify@example.com',
            'phone': '1234567890',
            'station_id': self.station.id,
            'host_id': self.employee_1.id,
            'check_in': check_in_time,
        }
        with self.mockSMSGateway():
            visitor1 = self.env['frontdesk.visitor'].create(visitor_data)

        visitor_sms = visitor1.message_ids.filtered(lambda m: m.message_type == 'sms')
        self.assertEqual(len(visitor_sms), 1, "Visitor should receive 1 SMS when host is on leave")
