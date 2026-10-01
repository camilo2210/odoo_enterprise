from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.fields import Command

from odoo.addons.pos_restaurant.tests.test_frontend import TestFrontendCommon


class TestPoSPlatformOrderCommon(TestFrontendCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider_demo = cls.env['platform.order.provider'].create({
            'name': 'Demo Provider',
            'code': 'none',
            'state': 'test',
        })

        cls.store_demo = cls.env['platform.order.entity'].create({
            'name': 'Demo Store',
            'external_id': 'store_001',
            'provider_id': cls.provider_demo.id,
            'config_id': cls.pos_config.id,
        })


class TestFrontend(TestPoSPlatformOrderCommon):

    _test_user_groups = None  # FIXME list needed groups

    def _create_platform_order(self, order_name):
        PlatformOrderEntity = self.env.registry.models['platform.order.entity']
        new_order = {
            'order_name': order_name,
            'floating_order_name': order_name,
            'platform_order_ref': 'PO-12345678',
            'platform_order_status': 'new',
            'platform_order_pin': '8821',
            'general_customer_note': 'No spicy, please.',
            'order_type': 'delivery',
        }
        new_order_lines = [
            {
                'attribute_value_ids': [],
                'customer_note': 'Extra napkins, please.',
                'full_product_name': self.coca_cola_test.name,
                'product_id': self.coca_cola_test.id,
                'qty': 1,
                'price_unit': self.coca_cola_test.lst_price,
                'price_subtotal': self.pos_config.currency_id.round(self.coca_cola_test.lst_price),
                'price_subtotal_incl': self.pos_config.currency_id.round(self.coca_cola_test.lst_price),
                'tax_ids': [Command.set(self.coca_cola_test.taxes_id.ids)],
            },
        ]
        with patch.object(PlatformOrderEntity, '_prepare_order_values_from_data', return_value=new_order),\
             patch.object(PlatformOrderEntity, '_prepare_order_lines_values_from_data', return_value=new_order_lines),\
             patch.object(PlatformOrderEntity, '_find_or_create_partners_from_data', return_value=self.env['res.partner']):
            return self.store_demo._create_order_from_data({})

    def test_platform_order_flow(self):
        self.env["pos.printer"].search([]).unlink()
        self.pos_config.with_user(self.pos_user).open_ui()

        PosOrder = self.env.registry.models['pos.order']

        def mark_platform_prep_order_as_printed_patch(self):
            try:
                return super(PosOrder, self).mark_platform_prep_order_as_printed()  # type: ignore[reportAttributeAccessIssue]
            except UserError:
                return False

        self._create_platform_order("Platform Order #001")
        with patch.object(PosOrder, '_send_accept_order_request', return_value=True), \
             patch.object(PosOrder, '_send_food_ready_request', return_value=True), \
             patch.object(PosOrder, 'mark_platform_prep_order_as_printed', mark_platform_prep_order_as_printed_patch):
            self.start_pos_tour("test_platform_order_flow")

        self._create_platform_order("Platform Order #002")
        with patch.object(PosOrder, '_send_reject_order_request', return_value=True), \
             patch.object(PosOrder, 'mark_platform_prep_order_as_printed', mark_platform_prep_order_as_printed_patch):
            self.start_pos_tour("test_platform_order_reject_flow")
