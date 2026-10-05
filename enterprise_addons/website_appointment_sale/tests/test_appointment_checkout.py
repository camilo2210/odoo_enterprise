# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.appointment_account_payment.tests.common import AppointmentAccountPaymentCommon
from odoo.addons.website_appointment_sale.controllers.appointment import WebsiteAppointmentSale
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.tests.common import MockRequest, WebsiteSaleCommon


@tagged('post_install', '-at_install')
class TestAppointmentCheckout(WebsiteSaleCommon, AppointmentAccountPaymentCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Controller = WebsiteSale()

    def test_checkout_impossible_if_booking_is_unavailable(self):
        # Two partners compete for the same booking slot
        partner1, partner2 = self._create_partner(), self._create_partner()
        so1 = self._create_so(partner_id=partner1.id)
        so2 = self._create_so(partner_id=partner2.id)
        so1._cart_add(
            product_id=self.appointment_users_payment.product_id.id,
            quantity=1,
            calendar_booking_id=self._create_user_booking(partner_id=partner1.id).id,
        )
        so2._cart_add(
            product_id=self.appointment_users_payment.product_id.id,
            quantity=1,
            calendar_booking_id=self._create_user_booking(partner_id=partner2.id).id,
        )
        so2.action_confirm()  # Partner 2 validates his booking first

        website = self.website.with_user(self.public_user)
        with MockRequest(website.env, website=website, path='/shop/payment', sale_order_id=so1.id):
            response = self.Controller.shop_payment()  # Partner 1 then tries to pay to confirm

        self.assertEqual(response.status_code, 303, 'SEE OTHER')
        self.assertURLEqual(response.location, '/shop/cart')  # Needs to update his cart

    @classmethod
    def _create_user_booking(cls, **values):
        return cls.env['calendar.booking'].create({
            'appointment_type_id': cls.appointment_users_payment.id,
            'duration': 1.0,
            'partner_id': cls.apt_manager.partner_id.id,
            'product_id': cls.appointment_users_payment.product_id.id,
            'staff_user_id': cls.staff_user_bxls.id,
            'start': cls.start_slot,
            'stop': cls.stop_slot,
            'booking_line_ids': [
                Command.create({
                    'appointment_user_id': cls.staff_user_bxls.id,
                    'capacity_reserved': 1,
                    'capacity_used': 1,
                })
            ],
            **values,
        })

    def test_redirect_to_payment_accessory_products(self):
        """ Test redirect target from _redirect_to_payment depending on accessory products presence. """
        accessory_product = self.env['product.product'].create({
            'name': 'Accessory Item',
            'type': 'consu',
        })
        partner_test = self._create_partner()

        cases = [
            ('no_accessories', False, '/shop/checkout?try_skip_step=true'),
            ('with_accessories', accessory_product.ids, '/shop/cart'),
        ]

        for name, accessory_product_ids, expected_url in cases:
            with self.subTest(name=name):
                self.appointment_users_payment.product_id.product_tmpl_id.accessory_product_ids = accessory_product_ids
                booking = self._create_user_booking(partner_id=partner_test.id)
                website = self.website.with_user(self.public_user)

                with MockRequest(website.env, website=website):
                    response = WebsiteAppointmentSale()._redirect_to_payment(booking)

                self.assertEqual(response.status_code, 303)
                self.assertIn(expected_url, response.location)
