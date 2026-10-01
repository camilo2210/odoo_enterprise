from odoo import Command

from odoo.tests import Form, tagged
from odoo.addons.repair.tests.test_repair import TestRepairCommon


@tagged('post_install', '-at_install')
class TestQualityRepair(TestRepairCommon):

    def test_repair_w_lot_and_quality_check(self):
        """Test quality check creation and flow on repair order"""

        self.env['quality.point'].create({
            'name': 'QP1',
            'measure_on': 'product',
            'picking_type_ids': [Command.set([self.stock_warehouse.repair_type_id.id])],
        })
        repair = self.env['repair.order'].create({
            'product_id': self.product_storable_lot.id,
            'partner_id': self.res_partner_1.id,
        })
        quant = self.create_quant(self.product_storable_lot, 1)
        quant.action_apply_inventory()
        repair.lot_id = quant.lot_id
        repair.action_validate()
        self.assertEqual(repair.state, 'confirmed')
        # Quality check should be created at repair confirmation
        qc = repair.quality_check_ids
        lot_1 = repair.lot_id
        self.assertEqual(len(qc), 1)
        self.assertEqual(lot_1.ids, qc.lot_ids.ids)

        # Reset repair lot
        repair.lot_id = False
        self.assertFalse(qc.lot_ids)
        repair.action_generate_serial()
        lot_2 = repair.lot_id
        self.assertNotEqual(lot_1, lot_2)
        self.assertEqual(lot_2.ids, qc.lot_ids.ids)

        # 'Pass' Quality Checks of repair order.
        qc.do_pass()
        self.assertEqual(qc.quality_state, 'pass')
        repair.action_repair_end()
        self.assertEqual(repair.state, 'done')

    def test_repair_multi_record_create_write(self):
        """Test that creating and writing multiple repair orders works as expected."""
        repairs = self.env['repair.order'].create([
            {
                'product_id': self.product_storable_lot.id,
                'partner_id': self.res_partner_1.id,
            },
            {
                'product_id': self.product_storable_lot.id,
                'partner_id': self.res_partner_1.id,
            },
        ])
        self.assertEqual(len(repairs), 2, "Model should create two repair orders.")

        repairs.write({'name': 'test'})
        self.assertEqual(set(repairs.mapped('name')), {'test'}, "Model should write the name on both records.")

    def test_repair_qc_failure_location(self):
        """Ensure that when a quality check measured on a product or operation
           and in a Repair Order is marked as failed, the selected failure location is
           correctly applied as the destination location of the final repair product move."""
        self.env['quality.point'].create({
            'measure_on': 'product',  # or 'operation'
            'picking_type_ids': [Command.link(self.stock_warehouse.repair_type_id.id)],
            'failure_location_ids': [Command.link(self.stock_location_14.id)],
        })
        repair = self.repair0
        repair.action_validate()
        qc = repair.quality_check_ids
        # Open the quality check wizard and fail the quality check
        wizard = Form.from_action(self.env, qc.action_open_quality_check_wizard()).save().do_fail()
        Form.from_action(self.env, wizard).save().confirm_fail()
        repair.action_repair_end()
        self.assertRecordValues(qc, [{
            'quality_state': 'fail',
            'product_id': self.product_product_5.id,
            'failure_location_id': self.stock_location_14.id,
        }])
        failure_move_line = self.env['stock.move.line'].search([
            ('product_id', '=', repair.product_id.id),
            ('location_dest_id', '=', self.stock_location_14.id),
            ('state', '=', 'done'),
        ])
        self.assertEqual(repair.product_qty, failure_move_line.qty_done)
