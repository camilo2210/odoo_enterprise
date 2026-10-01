# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.delivery.tests.common import DeliveryCommon


class ShiprocketCommon(DeliveryCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shiprocket = cls.env.ref('delivery_shiprocket.delivery_carrier_shiprocket')
