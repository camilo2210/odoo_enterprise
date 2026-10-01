# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import Command
from odoo.addons.pos_enterprise.tests.test_frontend import TestPreparationDisplayHttpCommon
from odoo.addons.pos_urban_piper.tests.test_frontend import TestFrontendUrbanPiper


class TestUrbanPiperPreparationDisplay(TestFrontendUrbanPiper, TestPreparationDisplayHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdis.pos_config_ids = [Command.set(cls.urban_piper_config.ids)]

    def test_preparation_display_future_delivery_order(self):
        self.urban_piper_config.open_ui()
        order = self.create_urbanpiper_order()
        order.preset_time = datetime.now() + timedelta(minutes=10)

        self.start_pos_tour('test_pos_urbanpiper_future_delivery_order', pos_config=self.urban_piper_config)
        self.env['pos.prep.order'].update_last_order_change(order)
        self.start_pdis_tour('test_preparation_display_future_delivery_order', login='pos_admin')
        prep_order = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)])
        self.assertEqual(len(prep_order), 1)
