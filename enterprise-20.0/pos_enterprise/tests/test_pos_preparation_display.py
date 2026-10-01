# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged
from odoo.addons.pos_enterprise.tests.test_frontend import TestPreparationDisplayHttpCommon
from odoo import Command, fields


@tagged('post_install', '-at_install')
class TestPosPreparationDisplay(TestPoSCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config

    def test_load_preparation_display_model(self):

        config1 = self.env['pos.config'].create({
            'name': 'rest1',
            'active': False
        })
        config2 = self.env['pos.config'].create({
            'name': 'rest2'
        })
        config3 = self.env['pos.config'].create({
            'name': 'rest3'
        })
        config4 = self.env['pos.config'].create({
            'name': 'rest4'
        })

        # pos preperation display linked to specific configs
        display1 = self.env['pos.prep.display'].create({
            'name': 'Preparation Display 1',
            'pos_config_ids': [Command.link(config1.id)]
        })
        display2 = self.env['pos.prep.display'].create({
            'name': 'Preparation Display 2',
            'pos_config_ids': [Command.link(config2.id)]
        })
        display3 = self.env['pos.prep.display'].create({
            'name': 'Preparation Display 3',
            'pos_config_ids': []
        })
        display4 = self.env['pos.prep.display'].create({
            'name': 'Preparation Display 4',
            'pos_config_ids': [Command.link(config3.id)]
        })

        config2.open_ui()
        config3.open_ui()
        config4.open_ui()

        self.assertEqual({d['id'] for d in config2.current_session_id.load_data({'only_records': True})['pos.prep.display']},
                         {display1.id, display2.id, display3.id})
        self.assertEqual({d['id'] for d in config3.current_session_id.load_data({'only_records': True})['pos.prep.display']},
                         {display1.id, display3.id, display4.id})
        self.assertEqual({d['id'] for d in config4.current_session_id.load_data({'only_records': True})['pos.prep.display']},
                         {display1.id, display3.id})

    def test_preparation_updated_on_stage_change(self):
        prep_display = self.env['pos.prep.display'].create({
            'name': 'Preparation Display 1',
            'pos_config_ids': [Command.link(self.config.id)],
            'stage_ids': [
                Command.create({'name': 'To Cook', 'sequence': 1}),
                Command.create({'name': 'Ready', 'sequence': 2}),
                Command.create({'name': 'Completed', 'sequence': 3}),
            ],
        })
        first_stage, second_stage, final_stage = prep_display.stage_ids

        self.open_new_session()
        order = next(iter(self._create_orders([{'pos_order_lines_ui_args': [(self.product, 1)]}]).values()))
        order_line = order.lines[0]
        # Simulate sending the order to preparation
        self.env['pos.prep.order'].update_last_order_change(order)

        prep_line = self.env['pos.prep.line'].search([('pos_order_line_id', '=', order_line.id)])
        self.assertEqual(prep_line.stage_id, first_stage)
        self.assertEqual(order_line.preparation_time, -1)
        self.assertEqual(order_line.service_time, -1)
        # Move order from first -> second stage
        prep_line.change_prep_line_stage(prep_display.id)
        prep_line._compute_stage_position()
        self.assertEqual(prep_line.stage_id, second_stage)
        self.assertNotEqual(order_line.preparation_time, -1)
        self.assertEqual(order_line.service_time, -1)
        # Move order from second -> final stage
        prep_line.change_prep_line_stage(prep_display.id)
        prep_line._compute_stage_position()
        self.assertEqual(prep_line.stage_id, final_stage)
        self.assertNotEqual(order_line.service_time, -1)

    def test_invoiced_order_sent_to_preparation(self):
        self.env['pos.prep.display'].create({
            'name': 'Preparation Display',
            'pos_config_ids': [Command.link(self.config.id)],
        })
        self.open_new_session()
        order = next(iter(self._create_orders([{
            'pos_order_lines_ui_args': [(self.product, 1)],
            'pos_order_ui_args': {'state': 'paid'},
            'customer': self.customer,
            'is_invoiced': True,
        }]).values()))
        self.assertTrue(order.account_move)
        prep_line = order.prep_order_ids.prep_line_ids
        self.assertEqual(prep_line.product_id, self.product)
        self.assertEqual(prep_line.quantity, 1)


@tagged('post_install', '-at_install')
class TestPdisCategorySelection(TestPreparationDisplayHttpCommon):

    def _make_order(self, session, lines):
        return self.env['pos.order'].create({
            'session_id': session.id,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_tax': 0,
            'amount_return': 0,
            'date_order': fields.Datetime.now(),
            'lines': [
                Command.create({
                    'product_id': product.id,
                    'qty': qty,
                    'price_unit': 1,
                    'price_subtotal': qty,
                    'price_subtotal_incl': qty,
                    'tax_ids': [],
                }) for product, qty in lines
            ],
        })

    def _make_prep_line(self, prep_order, order_line):
        return self.env['pos.prep.line'].create({
            'quantity': order_line.qty,
            'prep_order_id': prep_order.id,
            'pos_order_line_id': order_line.id,
            'product_id': order_line.product_id.id,
        })

    def test_prep_line_pdis_selection_by_category(self):
        """A prep line must only land on displays that match its product category."""
        self.pdis.write({'category_ids': [Command.set([self.pos_cat_desk_test.id])]})
        chair_display = self.pdis.copy({'name': 'Chair Display'})
        chair_display.write({'category_ids': [Command.set([self.pos_cat_chair_test.id])]})

        self.main_pos_config.open_ui()
        session = self.main_pos_config.current_session_id
        order = self._make_order(session, [
            (self.desk_pad.product_variant_id, 1),
            (self.letter_tray.product_variant_id, 1),
        ])
        prep_order = self.env['pos.prep.order'].create({'pos_order_id': order.id})

        desk_line = self._make_prep_line(prep_order, order.lines[0])
        chair_line = self._make_prep_line(prep_order, order.lines[1])

        self.assertEqual(desk_line.prep_display_ids, self.pdis,
            "Desk product must only be assigned to the desk display")
        self.assertEqual(chair_line.prep_display_ids, chair_display,
            "Chair product must only be assigned to the chair display")
