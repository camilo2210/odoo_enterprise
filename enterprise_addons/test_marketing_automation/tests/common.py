# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mass_mailing_sms.tests.common import MassSMSCommon
from odoo.addons.marketing_automation.tests.common import MarketingAutomationCase, MarketingAutomationCommon
from odoo.addons.marketing_automation_whatsapp.tests.common import MarketingAutomationWACase
from odoo.addons.sms_twilio.tests.common import MockSmsTwilioApi
from odoo.addons.whatsapp.tests.common import WhatsAppCommon, MockIncomingWhatsApp


class TestMACommon(
    MarketingAutomationCommon,
    MarketingAutomationCase,
    MarketingAutomationWACase,
    WhatsAppCommon,
    MassSMSCommon,
    MockIncomingWhatsApp,
    MockSmsTwilioApi,
):

    @classmethod
    def setUpClass(cls):
        """ Note that MailCommon is multi-company by default """
        super().setUpClass()
        cls.setUpWhatsapp()

        # ensure company / users data for tests, don't rely on demo
        cls.company_admin.write({
            'country_id': cls.env.ref('base.be'),
        })

        # ensure batch size for generation to have deterministic tests and check iterative behavior
        cls.env["ir.config_parameter"].sudo().set_int("mail.batch_size", 50)
        cls.env["ir.config_parameter"].sudo().set_int("marketing.execute.batch.size", 100)  # trace execution
        cls.env["ir.config_parameter"].sudo().set_int("marketing.trace.batch.size", 50)  # trace generation

    # ------------------------------------------------------------
    # ASSERTS
    # ------------------------------------------------------------

    def assertMarketAutoTraces(self, participants_info, activity, strict=True, canceled_res_ids=None, **trace_values):
        traces = super().assertMarketAutoTraces(participants_info, activity, strict=strict, canceled_res_ids=canceled_res_ids, **trace_values)
        for info in participants_info:
            if not info.get('trace_status'):
                continue
            if activity.activity_type == 'sms':
                self.assertMarketAutoTracesSMS(info, activity, traces)
            elif activity.activity_type == 'whatsapp':
                self.assertMarketAutoTracesWhatsapp(info, activity, traces)

    def assertMarketAutoTracesSMS(self, participant_info, activity, traces):
        numbers = participant_info.get('records_to_number', {})
        partners = participant_info.get('records_to_partner', {})

        self.assertSMSTraces(
            [
                {
                    'check_sms': participant_info.get('check_sms', True),
                    'content': participant_info.get('trace_content'),
                    'failure_reason': participant_info.get('trace_failure_reason', False),
                    'failure_type': participant_info.get('trace_failure_type', False),
                    'number': numbers.get(record.id, participant_info.get('trace_sms_number', record.phone_sanitized)),
                    'partner': partners.get(record.id, record.customer_id),
                    'record': record,
                    'sms_values': participant_info.get('sms_values'),
                    'trace_status': participant_info['trace_status'],
                    'trace_values': participant_info.get('mailing_trace_values'),
                } for record in participant_info['records']
            ],
            activity.mass_mailing_id,
            participant_info['records'],
            sent_unlink=participant_info.get('sent_unlink', True),
        )

    def assertMarketAutoTracesWhatsapp(self, participant_info, activity, traces):
        numbers = participant_info.get('records_to_number', {})
        partners = participant_info.get('records_to_partner', {})
        wa_from_mock = participant_info.get('wa_from_mock', True)
        trace_status = participant_info.get('trace_status')
        wa_msg_failure_type = participant_info.get('trace_failure_type', False)
        wa_msg_failure_reason = participant_info.get('trace_failure_reason', False)
        wa_msg_values = participant_info.get('wa_msg_values') or {}

        status_mapping = {
            'bounce': 'bounced',
        }

        for record in participant_info['records']:
            phone_number = numbers.get(record.id, record.phone)  # improve me
            _partner = partners.get(record.id, self.env['res.partner'])  # improve me

            fields_values = {
                'failure_reason': wa_msg_failure_reason,
                'failure_type': wa_msg_failure_type,
                'message_type': 'outbound',
                'mobile_number': phone_number,
                # 'mobile_number_formatted': phone_number,  # strange WA formatting, not sure we need to assert it here
                'wa_template_id': activity.whatsapp_template_id,
            }
            mail_message_values = {
                'message_type': 'whatsapp_message',
            }
            # check content aka generated body
            if participant_info.get('trace_content'):
                fields_values['body'] = participant_info['trace_content']
                mail_message_values['body'] = participant_info['trace_content']
            fields_values.update(**wa_msg_values)

            wa_status = fields_values.pop('state', False) or status_mapping.get(trace_status, trace_status)

            if wa_from_mock:
                self.assertWAMessageFromRecord(
                    record,
                    status=wa_status,
                    fields_values=fields_values,
                    mail_message_values=mail_message_values,
                )
            else:
                trace = traces.filtered(lambda t: t.res_id == record.id)
                wa_msg = trace.whatsapp_message_id
                self.assertTrue(wa_msg)
                self._assertWAMessage(
                    wa_msg, status=wa_status,
                    fields_values=fields_values,
                    mail_message_values=mail_message_values,
                )

    # ------------------------------------------------------------
    # RECORDS TOOLS
    # ------------------------------------------------------------

    @classmethod
    def _create_marketauto_records(cls, model='marketing.test.sms', count=1, include_void=True, include_dupe=False):
        """ Create records for marketing automation. Each batch consists in

          * 3 records with a valid partner w mobile and email;
          * 1 record without partner w email and mobile;
          * 1 record without partner
          *  -> wo email and mobile if include_void
          *  -> w  email and mobile = first record if include_dupe
          *  -> w  email and mobile generated else
        """
        record_vals = []
        for idx in range(0, count):
            for inner_idx in range(0, 5):
                current_idx = idx * 5 + inner_idx
                customer_name = f'Customer_{current_idx:06d}'
                record_name = f'Test_{current_idx:06d}'

                if inner_idx < 3:
                    email = f'email_{current_idx:06d}@customer.example.com'
                    partner = cls.env['res.partner'].create({
                        'country_id': cls.env.ref('base.be').id,
                        'email': f'"{customer_name}" <{email}>',
                        'name': customer_name,
                        'phone': f'0456{current_idx:06d}',
                    })
                else:
                    partner = cls.env['res.partner']

                vals = {
                    'customer_id': partner.id,
                    'description': f'Linked to partner {partner.name}' if partner else '',
                    'name': record_name,
                }
                if inner_idx == 3 or (inner_idx == 4 and not include_void and not include_dupe):
                    vals['email_from'] = f'"{customer_name}" <nopartner.email_{current_idx:06d}@customer.example.com>'
                    vals['phone'] = f'+32456{current_idx:06d}'
                elif inner_idx == 4 and include_dupe:
                    dupe_idx = current_idx - 4
                    vals['email_from'] = f'"Customer_{dupe_idx:06d}" <email_{dupe_idx:06d}@customer.example.com>'
                    vals['phone'] = f'+32456{dupe_idx:06d}'

                record_vals.append(vals)

        return cls.env[model].create(record_vals)
