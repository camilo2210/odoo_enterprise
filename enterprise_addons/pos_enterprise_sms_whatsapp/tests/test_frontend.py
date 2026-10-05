
from odoo import Command
from odoo.addons.pos_enterprise.tests.test_frontend import TestPreparationDisplayHttpCommon
from odoo.addons.pos_restaurant.tests import test_frontend
from odoo.addons.sms.tests.common import SMSCase
from odoo.addons.whatsapp.tests.common import WhatsAppCase
import odoo.tests


@odoo.tests.tagged('post_install', '-at_install')
class TestPDisCommunication(test_frontend.TestFrontendCommon, TestPreparationDisplayHttpCommon, SMSCase, WhatsAppCase):
    _test_user_groups = None  # FIXME list needed groups

    def setUp(self):
        super().setUp()

        self.preset_dine_in = self.env['pos.preset'].create({
            'name': 'Dine in',
            'available_in_self': True,
            'service_at': 'table',
        })
        self.preset_takeaway = self.env['pos.preset'].create({
            'name': 'Takeaway',
            'available_in_self': True,
            'service_at': 'counter',
            'identification': 'name',
        })
        self.pos_config.write({
            'self_ordering_mode': 'mobile',
            'use_presets': True,
            'default_preset_id': self.preset_takeaway.id,
            'available_preset_ids': [(6, 0, [self.preset_takeaway.id, self.preset_dine_in.id])],
        })

    def test_sms_received_pdis(self):
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
            'sms_enabled': True,
            'whatsapp_enabled': True,
            'category_ids': [Command.set(self.env['pos.category'].search([]).ids)],
        })

        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, "takeaway_order_with_phone")

        order = self.env['pos.order'].search([('partner_id.phone', '=', '+32455667788')], limit=1)
        self.assertTrue(order, "The self-order should create an order linked to the provided phone number.")
        expected_number = order.partner_id._phone_format(number=order.partner_id.phone) or order.partner_id.phone
        sms_messages = self.env['sms.sms'].search([
            ('number', '=', expected_number)
        ])
        self.assertTrue(sms_messages, "A SMS should be sent to the customer's phone number.")

        pdis_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        pdis_order.prep_line_ids.sudo().change_prep_line_stage(self.pdis.id, direction=1)

        sms_order_received_template = self.env.ref('pos_enterprise_sms_whatsapp.sms_template_order_received_confirmation_pos')
        sms_order_ready_template = self.env.ref('pos_enterprise_sms_whatsapp.sms_template_order_ready_pos')
        sms_order_received_body = sms_order_received_template._render_field('body', [order.id], compute_lang=True)[order.id]
        sms_order_ready_body = sms_order_ready_template._render_field('body', [order.id], compute_lang=True)[order.id]

        sms_received_message = self.env['sms.sms'].search([('number', '=', expected_number)]).filtered(lambda sms: sms.body == sms_order_received_body)
        self._new_sms = sms_received_message
        self.assertSMS(order.partner_id, expected_number, sms_received_message.state, fields_values={'body': sms_order_received_body})

        sms_ready_message = self.env['sms.sms'].search([('number', '=', expected_number)]).filtered(lambda sms: sms.body == sms_order_ready_body)
        self._new_sms = sms_ready_message
        self.assertSMS(order.partner_id, expected_number, sms_ready_message.state, fields_values={'body': sms_order_ready_body})

    def test_whatsapp_received_pdis(self):
        self.pdis.write({
            'pos_config_ids': [(4, self.pos_config.id)],
            'sms_enabled': True,
            'whatsapp_enabled': True,
            'category_ids': [Command.set(self.env['pos.category'].search([]).ids)],
        })

        self.pos_config.with_user(self.pos_user).open_ui()
        self.pos_config.current_session_id.set_opening_control(0, "")
        self_route = self.pos_config._get_self_order_route()
        self.start_tour(self_route, "takeaway_order_with_phone")

        order = self.env['pos.order'].search([('partner_id.phone', '=', '+32455667788')], limit=1)
        self.assertTrue(order, "The self-order should create an order linked to the provided phone number.")
        whatsapp_messages = self.env['whatsapp.message'].sudo().search([
            ('mobile_number', '=', order.partner_id.phone)
        ])
        self.assertTrue(whatsapp_messages, "A WhatsApp message should be sent to the customer's phone number.")

        pdis_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)], limit=1)
        pdis_order.prep_line_ids.sudo().change_prep_line_stage(self.pdis.id, direction=1)

        whatsapp_order_received_template = self.env.ref('pos_enterprise_sms_whatsapp.whatsapp_order_received_confirmation_pos')
        whatsapp_order_ready_template = self.env.ref('pos_enterprise_sms_whatsapp.whatsapp_order_ready_confirmation_pos')
        whatsapp_received_message = self.env['whatsapp.message'].sudo().search([('mobile_number', '=', order.partner_id.phone)]).filtered(lambda msg: msg.wa_template_id == whatsapp_order_received_template)
        self._new_wa_msg = whatsapp_received_message
        self.assertWAMessageFromNumber(order.partner_id.phone, status=whatsapp_received_message.state, fields_values={
            'wa_template_id': whatsapp_order_received_template,
        })

        whatsapp_ready_message = self.env['whatsapp.message'].sudo().search([('mobile_number', '=', order.partner_id.phone)]).filtered(lambda msg: msg.wa_template_id == whatsapp_order_ready_template)
        self._new_wa_msg = whatsapp_ready_message
        self.assertWAMessageFromNumber(order.partner_id.phone, status=whatsapp_ready_message.state, fields_values={
            'wa_template_id': whatsapp_order_ready_template,
        })
