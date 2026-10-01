# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.delivery_ups_rest.tests.common import DeliveryUPSCommon
from odoo.addons.payment_custom.tests.common import PaymentCustomCommon


@tagged('post_install', '-at_install')
class TestCashOnDeliveryPaymentProvider(DeliveryUPSCommon, PaymentCustomCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_when_ups_cod_enabled_only_cod_pms_are_available(self):
        self.ups_delivery.allow_cash_on_delivery = True
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'carrier_id': self.ups_delivery.id,
        })
        available_providers = self.env['payment.provider'].sudo()._find_available_providers(
            self.company.id, self.partner.id, self.amount, sale_order_id=order.id
        )
        self.assertTrue(all(p.custom_mode == 'cash_on_delivery' for p in available_providers))
