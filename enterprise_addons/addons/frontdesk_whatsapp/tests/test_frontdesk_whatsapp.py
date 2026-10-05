# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.addons.whatsapp.tests.common import WhatsAppCommon


class TestFrontdeskWhatsapp(WhatsAppCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.company = cls.env['res.company'].create({
            'name': 'WhatsApp Test Company',
            'email': 'whatsapp.company@example.com',
            'country_id': cls.env.ref('base.us').id,
        })
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.partner_1 = cls.env['res.partner'].create({
            'name': 'WhatsApp Test Partner 1',
            'email': 'whatsapptest1@example.com',
        })
        cls.user_1 = cls.env['res.users'].create({
            'name': 'WhatsApp Test User 1',
            'login': 'whatsapp_test_user_1',
            'partner_id': cls.partner_1.id,
        })
        cls.employee_1, cls.employee_3 = cls.env['hr.employee'].create([{
            'name': 'WhatsApp Host 1',
            'user_id': cls.user_1.id,
            'work_phone': '+32456000011',
            'work_email': 'host@example.com',
            'company_id': cls.company.id,
        }, {
            'name': 'WhatsApp Host 3',
            'work_email': False,
            'work_phone': False,
            'company_id': cls.company.id,
        }])

        cls.whatsapp_template = cls.env['whatsapp.template'].create({
            'name': 'Frontdesk WhatsApp Template Test',
            'model_id': cls.env['ir.model']._get_id('frontdesk.visitor'),
            'body': 'Hello {{1}}',
            'status': 'approved',
            'wa_account_id': cls.whatsapp_account.id,
            'variable_ids': [
                (0, 0, {
                    'name': '{{1}}',
                    'line_type': 'body',
                    'field_type': 'field',
                    'field_name': 'name',
                    'demo_value': 'Test',
                })
            ]
        })

        cls.station = cls.env['frontdesk.frontdesk'].create({
            'name': 'WhatsApp Notify Test Station',
            'responsible_ids': [(4, cls.admin.id)],
            'notify_whatsapp': True,
            'ask_phone': True,
            'ask_email': True,
            'host_selection': True,
            'company_id': cls.company.id,
            'whatsapp_template_id': cls.whatsapp_template.id,
            'host_ids': [(4, cls.employee_1.id)],
        })

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------
    def test_host_with_no_user_whatsapp_fallback(self):
        '''Test that host without user falls back to WhatsApp when discuss is enabled
        and frontdesk_sms is not installed. When SMS is installed, it handles the fallback.'''
        host = self.env['hr.employee'].create({
            'name': 'Host with WhatsApp',
            'work_phone': '+32456000033',
            'company_id': self.company.id,
        })
        self.station.notify_discuss = True
        self.station.notify_email = False
        self.station.notify_whatsapp = False
        with self.mockWhatsappGateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_Fallback',
                'station_id': self.station.id,
                'host_id': host.id,
            })

        whatsapp_messages = self.env['whatsapp.message'].search([
            ('mobile_number_formatted', '=', '32456000033'),
        ])
        if 'notify_sms' in self.station._fields:
            # When frontdesk_sms is installed, SMS handles the discuss fallback
            self.assertEqual(len(whatsapp_messages), 0, "WhatsApp fallback should defer to SMS when SMS module is installed.")
        else:
            self.assertEqual(len(whatsapp_messages), 1, "Host without user should receive WhatsApp fallback.")

    def test_host_notify_whatsapp(self):
        '''Test that the host gets the notification through WhatsApp when visitor checks in'''
        with self.mockWhatsappGateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_1',
                'station_id': self.station.id,
                'host_id': self.employee_1.id,
            })
        whatsapp_messages = self.env['whatsapp.message'].search([
            ('mobile_number_formatted', '=', '32456000011'),
        ])
        self.assertEqual(len(whatsapp_messages), 1, "Exactly one WhatsApp message should be sent to the host.")

    def test_host_with_all_notify_true_send_whatsapp(self):
        '''If all notify settings are enabled, host without user_id but with phone gets WhatsApp'''
        host = self.env['hr.employee'].create({
            'name': 'Host All Channels',
            'work_email': 'host_all@example.com',
            'work_phone': '+32456000044',
            'company_id': self.company.id,
        })
        self.station.notify_discuss = True
        self.station.notify_email = True
        self.station.notify_whatsapp = True
        with self.mockWhatsappGateway():
            self.env['frontdesk.visitor'].create({
                'name': 'Visitor_7',
                'station_id': self.station.id,
                'host_id': host.id,
            })
        whatsapp_messages = self.env['whatsapp.message'].search([
            ('mobile_number_formatted', '=', '32456000044'),
        ])
        self.assertEqual(len(whatsapp_messages), 1, "Exactly one WhatsApp message should be sent to the host.")

    def test_constraint_with_invalid_hosts_whatsapp(self):
        '''The WhatsApp constraint triggers when host is missing phone number'''
        with self.assertRaises(ValidationError):
            self.station.write({
                'notify_whatsapp': True,
                'host_ids': [Command.link(self.employee_3.id)],
            })

    def test_check_and_notify_visitor_host_on_leave_whatsapp(self):
        '''Test that when host is on leave, visitor is notified via WhatsApp'''
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
            'name': 'Visitor_Notify_WhatsApp',
            'email': 'visitornotify@example.com',
            'phone': '+32456000022',
            'station_id': self.station.id,
            'host_id': self.employee_1.id,
            'check_in': check_in_time,
        }
        with self.mockWhatsappGateway():
            visitor = self.env['frontdesk.visitor'].create(visitor_data)
        visitor_phone_formatted = visitor._whatsapp_phone_format(number=visitor.phone) or visitor.phone
        visitor_whatsapp = self.env['whatsapp.message'].search([
            ('mobile_number_formatted', '=', visitor_phone_formatted),
        ])
        self.assertEqual(len(visitor_whatsapp), 1, "Visitor should receive 1 WhatsApp message when host is on leave.")
