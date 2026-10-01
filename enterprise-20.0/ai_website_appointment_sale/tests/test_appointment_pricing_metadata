# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command

from odoo.addons.appointment_account_payment.tests.common import AppointmentAccountPaymentCommon


class TestAIAppointmentPricingMetadata(AppointmentAccountPaymentCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env['ai.agent'].create({'name': 'AI Preview Agent'})

    def test_appointment_preview_metadata_inherits_product_pricing(self):
        appointment = self.appointment_users_payment
        appointment.product_id.write({
            'list_price': 80.0,
            'taxes_id': [Command.clear()],
        })
        pricelist = self.env['product.pricelist'].create({
            'name': 'AI Appointment Discount Pricelist',
            'currency_id': self.env.company.currency_id.id,
            'item_ids': [
                Command.create({
                    'applied_on': '1_product',
                    'product_tmpl_id': appointment.product_id.product_tmpl_id.id,
                    'compute_price': 'discount',
                    'price_discount': 25,
                }),
            ],
        })
        context = {
            'pricelist_id': pricelist.id,
            'website_id': self.ref('base.default_website'),
        }

        result = self.env['ai.tool'].with_context(**context)._ai_tool_prepare_record_previews(
            {'state': {}},
            'appointment.type',
            [{'id': appointment.id}],
        )
        expected_info = appointment.product_id.with_context(
            **context
        )._resolve_product_combination_info()[appointment.product_id.id]

        metadata, = result['preview_metadata']
        self.assertEqual(metadata['price'], expected_info['price'])
        self.assertEqual(metadata['list_price'], expected_info['list_price'])
        self.assertTrue(metadata['has_discounted_price'])
