# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command

from odoo.tests.common import tagged
from odoo.addons.quality_control.tests.test_common import TestQualityCommon
from odoo.addons.mrp_workorder.tests.test_shopfloor import TestShopFloor

@tagged('post_install', '-at_install')
class TestShopFloorQuality(TestQualityCommon, TestShopFloor):
    _test_user_groups = None  # FIXME list needed groups

    def test_shop_floor_spreadsheet(self):
        """ Ensure we can use spreadsheet from Shop Floor to handle quality check."""
        snow_leopard, leg = self.env['product.product'].create([{
            'name': 'Snow leopard',
            'is_storable': True,
        }, {
            'name': 'Leg',
            'is_storable': True,
        }])
        mountains = self.env['mrp.workcenter'].create({
            'name': 'Mountains',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        self.env['stock.quant']._update_available_quantity(leg, self.stock_location, quantity=100)
        bom = self.env['mrp.bom'].create({
            'product_id': snow_leopard.id,
            'product_tmpl_id': snow_leopard.product_tmpl_id.id,
            'uom_id': snow_leopard.uom_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({
                'name': 'op1',
                'workcenter_id': mountains.id,
            })],
            'bom_line_ids': [
                Command.create({'product_id': leg.id, 'product_qty': 4}),
            ]
        })
        picking_type = self.warehouse.manu_type_id
        spreadsheet = self.env['quality.spreadsheet.template'].create({
            'check_cell': 'A1',
            'name': 'my spreadsheet quality check template',
        })
        self.env['quality.point'].create([
            {
                'picking_type_ids': [Command.link(picking_type.id)],
                'product_ids': [Command.link(snow_leopard.id)],
                'operation_id': bom.operation_ids[0].id,
                'title': 'My spreadsheet check',
                'test_type_id': self.env.ref('quality_control.test_type_spreadsheet').id,
                'sequence': 0,
                'spreadsheet_template_id': spreadsheet.id,
            },
        ])
        mo = self.env['mrp.production'].create({
            'product_id': snow_leopard.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        self.start_tour('/odoo/shop-floor', 'test_shop_floor_spreadsheet', login='shop_floor_user')
        self.assertRecordValues(mo.workorder_ids[0].check_ids, [
            {'quality_state': 'fail'},
        ])

    def test_register_sn_production_quality_check(self):
        """ Generate a QC to register the production of a tracked by SN product
        and process that in Shop Floor."""
        self._enable_settings('tracking')
        final_product, component = self.env['product.product'].create([
            {
                'name': 'Lovely Product',
                'is_storable': True,
                'tracking': 'serial',
            },
            {
                'name': 'Lovely Component',
                'is_storable': True,
            },
        ])
        self.env['stock.quant']._update_available_quantity(component, self.stock_location, quantity=10)
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Lovely Workcenter',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Lovely Operation', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1.0}),
            ]
        })
        self.env['quality.point'].create([
            {
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'operation_id': bom.operation_ids.id,
                'title': 'Lovely Production Registering',
                'test_type_id': self.ref('mrp_workorder.test_type_register_production'),
                'sequence': 1,
            },
        ])
        mo = self.env['mrp.production'].create({
            'product_id': final_product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        self.assertEqual(mo.reservation_state, 'assigned')
        mo.button_plan()
        action = mo.workorder_ids.action_open_mes()
        url = '/web?#action=%s' % (action['id'])
        self.start_tour(url, "test_register_sn_production_quality_check", login='shop_floor_user')
        self.assertRecordValues(mo.lot_producing_ids, [{'name': 'SN0012'}])

    def test_display_quality_fail_message(self):
        """ Ensure the failure message is displayed correctly on the shop floor
        when a quality check fails."""
        finished_product, component_product = self.env["product.product"].create([
            {
                "name": "Finished Product",
                "is_storable": True,
            },
            {
                "name": "Component",
                "is_storable": True,
            },
        ])

        assembly_workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Workcenter'
        })
        bom_finished_product = self.env['mrp.bom'].create({
            'product_id': finished_product.id,
            'product_tmpl_id': finished_product.product_tmpl_id.id,
            'operation_ids': [
                Command.create({
                    'name': 'Assembly Step',
                    'workcenter_id': assembly_workcenter.id,
                })
            ],
            'bom_line_ids': [
                Command.create({
                    'product_id': component_product.id,
                    'product_qty': 4,
                })
            ],
        })

        self.env['stock.quant']._update_available_quantity(
            component_product, self.warehouse.lot_stock_id, quantity=100
        )

        self.env['quality.point'].create([{
            'product_ids': [Command.link(finished_product.id)],
            'operation_id': bom_finished_product.operation_ids[0].id,
            'title': 'Assembly Quality Check',
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id,
            'failure_message': 'This does not pass the quality check',
        }])

        self.env['mrp.production'].create({
            'product_id': finished_product.id,
            'product_qty': 1,
            'bom_id': bom_finished_product.id,
        }).action_confirm()

        self.start_tour('/odoo/shop-floor', 'test_quality_fail_message', login='shop_floor_user')

    def test_mass_produce_sn_with_backorders_and_qc(self):
        """ Make sure that mass producing a product with backorders works correctly.
        along with the execution of the quality checks.
        """
        self._enable_settings('tracking')
        product = self.env['product.product'].create({
            'name': 'Serial Gadget',
            'is_storable': True,
            'tracking': 'serial',
        })

        self.env['quality.point'].create({
            'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
            'product_ids': [Command.link(product.id)],
            'title': 'Final Inspection',
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id,
        })

        mo = self.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 3,
        })
        mo.action_confirm()

        self.start_tour('/odoo/shop-floor', "test_mass_produce_backorder_qc", login='shop_floor_user')

    def test_backorder_qc_without_auto_close(self):
        """Verify that when auto_close_production is False, quality checks
        function as expected, while the 'Produce' option remains unavailable.
        """
        self._enable_settings('tracking')
        manu_type = self.warehouse.manu_type_id
        manu_type.auto_close_production = False

        product = self.env['product.product'].create({
            'name': 'Serial Gadget',
            'is_storable': True,
            'tracking': 'serial',
        })

        self.env['quality.point'].create({
            'picking_type_ids': [Command.link(manu_type.id)],
            'product_ids': [Command.link(product.id)],
            'title': 'Final Inspection',
            'test_type_id': self.env.ref('quality_control.test_type_passfail').id,
        })

        mo = self.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 3,
            'picking_type_id': manu_type.id,
        })
        mo.action_confirm()

        self.start_tour('/odoo/shop-floor', "test_backorder_qc_without_auto_close", login='shop_floor_user')
