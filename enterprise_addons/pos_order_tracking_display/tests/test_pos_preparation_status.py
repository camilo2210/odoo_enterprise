# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@odoo.tests.tagged('post_install', '-at_install')
class TestPosPreparationStatusScreen(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config

    def test_load_preparation_status_orders(self):
        prep_display = self.env['pos.prep.display'].create({
            'name': 'Preparation Display 1',
            'pos_config_ids': [Command.link(self.config.id)],
            'stage_ids': [
                Command.create({'name': 'To Cook', 'sequence': 1}),
                Command.create({'name': 'Ready', 'sequence': 2}),
                Command.create({'name': 'Completed', 'sequence': 3}),
            ],
        })
        self.open_new_session()
        order = next(iter(self._create_orders([{'pos_order_lines_ui_args': [(self.product, 1)]}]).values()))
        # Simulate sending the order to preparation
        self.env['pos.prep.order'].update_last_order_change(order)
        prep_line = self.env['pos.prep.line'].search([('pos_order_line_id', '=', order.lines[0].id)])

        orders_status = prep_display._get_pos_orders()
        self.assertEqual(len(orders_status.get('done')), 0)
        self.assertEqual(len(orders_status.get('notDone')), 1)

        # Move order from first -> second stage
        prep_line.change_prep_line_stage(prep_display.id)
        orders_status = prep_display._get_pos_orders()
        self.assertEqual(len(orders_status.get('done')), 1)
        self.assertEqual(len(orders_status.get('notDone')), 0)

        # Move order from second -> final stage
        prep_line.change_prep_line_stage(prep_display.id)
        orders_status = prep_display._get_pos_orders()
        self.assertDictEqual(orders_status, {'done': [], 'notDone': [], 'ordersCompletedReadyDate': {}})
