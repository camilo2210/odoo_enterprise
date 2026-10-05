# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.test_whatsapp.tests.common import WhatsAppFullCase
from odoo.tests import tagged, users


@tagged('wa_template')
@tagged('at_install', '-post_install')  # LEGACY at_install
class WhatsAppTemplate(WhatsAppFullCase):

    @users('user_wa_admin')
    def test_template_phone_field_path_preserved(self):
        """Ensure a valid dotted path is not replaced by the fallback compute."""
        base_model = self.env['ir.model']._get_id('whatsapp.test.base')
        nophone_model = self.env['ir.model']._get_id('whatsapp.test.nophone')
        template = self.env['whatsapp.template'].create({
            'body': 'Hello Phone Field Path',
            'model_id': base_model,
            'name': 'WhatsApp Template Path',
            'phone_field': 'customer_id.phone',
            'status': 'approved',
            'use_default_recipient': False,
            'wa_account_id': self.whatsapp_account.id,
        })

        template.write({'model_id': nophone_model})
        self.assertEqual(template.phone_field, 'customer_id.phone')

        template.write({'model_id': base_model})
        self.assertEqual(template.phone_field, 'customer_id.phone')

    @users('user_wa_admin')
    def test_template_recipient_number_resolution(self):
        """ Test recipient number resolution with default recipient and phone_field chains. """
        template = self.env['whatsapp.template'].create({
            'body': 'Hello Phone Field Chain',
            'name': 'WhatsApp Template',
            'template_name': 'Phone Field Chain',
            'status': 'approved',
            'wa_account_id': self.whatsapp_account.id,
        })

        test_nophone_record_with_partner = self.env['whatsapp.test.nophone'].create({
            'country_id': self.test_partner.country_id.id,
            'customer_id': self.test_partner.id,
            'name': "Test No Phone Field With partner",
        })

        for exp_mobile_field, exp_msg_status, test_record, tmpl_write_vals in [
            (
                # use_default_recipient: use the record phone resolved on the base model
                self.test_base_record_partner.customer_id.phone,
                "sent",
                self.test_base_record_partner,
                {
                    "model_id": self.env["ir.model"]._get_id("whatsapp.test.base"),
                    "phone_field": False,
                    "use_default_recipient": True,
                },
            ), (
                # use_default_recipient on a model without a phone field: falls back to partner's phone
                test_nophone_record_with_partner.customer_id.phone,
                "sent",
                test_nophone_record_with_partner,
                {
                    "model_id": self.env["ir.model"]._get_id("whatsapp.test.nophone"),
                    "phone_field": False,
                    "use_default_recipient": True,
                },
            ), (
                # use_default_recipient: use record phone when no partner is set
                self.test_base_record_nopartner.phone,
                "sent",
                self.test_base_record_nopartner,
                {
                    "model_id": self.env["ir.model"]._get_id("whatsapp.test.base"),
                    "phone_field": False,
                    "use_default_recipient": True,
                },
            ), (
                # with use_default_recipient disabled, use the template phone_field customer_id.phone
                self.test_base_record_partner.customer_id.phone,
                "sent",
                self.test_base_record_partner,
                {
                    "model_id": self.env["ir.model"]._get_id("whatsapp.test.base"),
                    "phone_field": "customer_id.phone",
                    "use_default_recipient": False,
                },
            ), (
                # with use_default_recipient disabled, customer_id.phone resolves to no value -> phone_invalid
                self.test_base_record_nopartner.customer_id.phone,
                "error",
                self.test_base_record_nopartner,
                {
                    "model_id": self.env["ir.model"]._get_id("whatsapp.test.base"),
                    "phone_field": "customer_id.phone",
                    "use_default_recipient": False,
                },
            ),
        ]:
            with self.subTest(test_record=test_record):
                template.write(tmpl_write_vals)
                composer = self._instanciate_wa_composer_from_records(template, test_record)
                with self.mockWhatsappGateway():
                    composer.action_send_whatsapp_template()
                self.assertWAMessageFromRecord(
                    test_record,
                    status=exp_msg_status,
                    fields_values={
                        'mobile_number': exp_mobile_field,
                    },
                )
