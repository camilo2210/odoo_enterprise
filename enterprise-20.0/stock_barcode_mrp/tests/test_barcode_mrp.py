# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged
from odoo.addons.stock_barcode.tests.test_barcode_client_action import TestBarcodeClientAction


@tagged('post_install', '-at_install')
class TestPickingBarcodeClientAction(TestBarcodeClientAction):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.component01, cls.component02, cls.component_lot, cls.simple_kit, cls.kit_lot = cls.env['product.product'].create([
            {
                'name': 'Compo 01',
                'is_storable': True,
                'barcode': 'compo01',
            }, {
                'name': 'Compo 02',
                'is_storable': True,
                'barcode': 'compo02',
            }, {
                'name': 'Compo Lot',
                'is_storable': True,
                'barcode': 'compo_lot',
                'tracking': 'lot',
            }, {
                'name': 'Simple Kit',
                'is_storable': True,
                'barcode': 'simple_kit',
            }, {
                'name': 'Kit Lot',
                'is_storable': True,
                'barcode': 'kit_lot',
            },
        ])

        cls.bom_kit_lot, cls.bom_simple_kit = cls.env['mrp.bom'].create([
            {
                'product_tmpl_id': cls.kit_lot.product_tmpl_id.id,
                'product_qty': 1.0,
                'type': 'phantom',
                'bom_line_ids': [
                    Command.create({'product_id': cls.component01.id, 'product_qty': 1.0}),
                    Command.create({'product_id': cls.component_lot.id, 'product_qty': 1.0}),
                ],
            }, {
                'product_tmpl_id': cls.simple_kit.product_tmpl_id.id,
                'product_qty': 1.0,
                'type': 'phantom',
                'bom_line_ids': [
                    Command.create({'product_id': cls.component01.id, 'product_qty': 1.0}),
                    Command.create({'product_id': cls.component02.id, 'product_qty': 1.0}),
                ],
            },
        ])

    def test_immediate_receipt_kit_from_scratch_with_tracked_compo(self):
        receipt_picking = self.env['stock.picking'].create({
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type_in.id,
        })
        url = self._get_client_action_url(receipt_picking)
        self.start_tour(url, 'test_immediate_receipt_kit_from_scratch_with_tracked_compo', login='admin', timeout=180)

        self.assertRecordValues(receipt_picking.move_ids.move_line_ids, [
            {'product_id': self.component01.id, 'qty_done': 3.0, 'lot_name': False, 'state': 'done'},
            {'product_id': self.component_lot.id, 'qty_done': 3.0, 'lot_name': 'super_lot', 'state': 'done'},
            {'product_id': self.component01.id, 'qty_done': 1.0, 'lot_name': False, 'state': 'done'},
            {'product_id': self.component02.id, 'qty_done': 1.0, 'lot_name': False, 'state': 'done'},
        ])

    def test_planned_receipt_kit_from_scratch_with_tracked_compo(self):
        receipt_picking = self.env['stock.picking'].create({
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type_in.id,
        })
        url = self._get_client_action_url(receipt_picking)
        self.start_tour(url, 'test_planned_receipt_kit_from_scratch_with_tracked_compo', login='admin', timeout=180)

        self.assertRecordValues(receipt_picking.move_ids.move_line_ids, [
            {'product_id': self.component01.id, 'qty_done': 3.0, 'lot_name': False, 'state': 'done'},
            {'product_id': self.component_lot.id, 'qty_done': 3.0, 'lot_name': 'super_lot', 'state': 'done'},
            {'product_id': self.component01.id, 'qty_done': 1.0, 'lot_name': False, 'state': 'done'},
            {'product_id': self.component02.id, 'qty_done': 1.0, 'lot_name': False, 'state': 'done'},
        ])

    def test_picking_product_with_kit_and_packaging(self):
        """ A picking with a move for a product with a kit BOM and packaging can be processed
        in Barcode
        """
        packaging = self.env['uom.uom'].create({
            'name': 'test packaging',
            'relative_factor': 1.0,
        })
        self.simple_kit.uom_ids = packaging

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_internal.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'move_ids': [Command.create({
                'product_id': self.simple_kit.id,
                'product_uom_qty': 1.0,
                'uom_id': self.simple_kit.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.stock_location.id,
            })],
        })
        picking.action_confirm()

        create_vals = []
        for stock_move, component in zip(picking.move_ids, picking.move_ids.mapped('product_id')):
            create_vals.append({
                'product_id': component.id,
                'picking_id': picking.id,
                'move_id': stock_move.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.stock_location.id,
                'quantity': 1.0,
            })

        self.env['stock.move.line'].create(create_vals)

        url = self._get_client_action_url(picking)
        self.start_tour(url, 'test_picking_product_with_kit_and_packaging', login='admin', timeout=180)
        self.assertEqual(picking.state, 'done')

    def test_picking_product_with_kit_and_component(self):
        """ A picking with a kit (comp A + comp B) and a separate move for a component(comp B) should not group the
        two lines (the comp B line linked to the kit and the comp B line from the comp B move) in Barcode
        """
        grp_lot = self.env.ref('stock.group_production_lot')
        self.env.user.write({'group_ids': [(4, grp_lot.id, 0)]})
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_internal.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'move_ids': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'uom_id': self.kit_lot.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.stock_location.id,
            }) for product in [self.kit_lot, self.component_lot]],
        })
        picking.action_confirm()
        picking.move_ids.write({'quantity': 1})
        url = self._get_client_action_url(picking)
        self.start_tour(url, 'test_picking_product_with_kit_and_component', login='admin', timeout=180)

    def test_delivery_kit_with_tracked_compo(self):
        """
        Test that unreserved scanned component lots overrides the initial reservation.
        """
        grp_lot = self.env.ref('stock.group_production_lot')
        self.env.user.group_ids |= grp_lot
        self.picking_type_out.show_reserved_sns = True
        self.bom_kit_lot.bom_line_ids = self.bom_kit_lot.bom_line_ids[-1]
        lots = self.env['stock.lot'].create([
            {
                'name': f"LOT00{i + 1}",
                'product_id': self.component_lot.id,
                'company_id': self.env.company.id
            } for i in range(4)
        ])
        for lot in lots:
            self.env['stock.quant']._update_available_quantity(product_id=self.component_lot, location_id=self.stock_location, quantity=1, lot_id=lot)
        delivery = self.env['stock.picking'].create({
            'name': 'WH/OUT/DKWTC',
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'move_ids': [
                Command.create({
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                    'uom_id': product.uom_id.id,
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id,
                }) for product in [self.kit_lot, self.component_lot]
            ],
        })
        delivery.action_confirm()
        self.start_tour('/odoo/barcode', 'test_delivery_kit_with_tracked_compo', login='admin')

    def test_picking_kit_variant_packaging(self):
        """ Test packaging related to a specific variant.
        """
        group_uom = self.env.ref('uom.group_uom')
        self.env.user.write({'group_ids': [Command.link(group_uom.id)]})
        att_color = self.env['product.attribute'].create({'name': 'Color', 'sequence': 1})
        att_color_values = self.env['product.attribute.value'].create([
            {'name': 'red', 'attribute_id': att_color.id},
            {'name': 'blue', 'attribute_id': att_color.id},
        ])
        product_template = self.bom_simple_kit.product_tmpl_id
        product_template.attribute_line_ids = self.env['product.template.attribute.line'].create([{
            'product_tmpl_id': product_template.id,
            'attribute_id': att_color.id,
            'value_ids': [
                Command.set(att_color_values.ids),
            ],
        }])
        blue_sofa = product_template.product_variant_ids[1]
        pack_2 = self.env['uom.uom'].create({
            'name': 'pack of two',
            'relative_factor': 2,
            'relative_uom_id': self.env.ref('uom.product_uom_unit').id,
        })
        self.env['product.uom'].create({
            'barcode': 'PACK02',
            'product_id': blue_sofa.id,
            'uom_id': pack_2.id,
        })
        picking = self.env['stock.picking'].create({
            'name': 'WH/IN/BLUESIMPLEKIT',
            'picking_type_id': self.picking_type_in.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'move_ids': [
                Command.create({
                    'product_id': blue_sofa.id,
                    'product_uom_qty': 2,
                    'uom_id': blue_sofa.uom_id.id,
                    'location_id': self.supplier_location.id,
                    'location_dest_id': self.stock_location.id,
                }),
            ],
        })
        picking.action_confirm()
        self.start_tour('/odoo/barcode', 'test_picking_kit_variant_packaging', login='admin')

    def test_only_mo_of_current_operation_are_visible(self):
        """Test that it only returns manufacturing orders for the given picking type."""
        picking_type_1 = self.warehouse.manu_type_id
        picking_type_2 = picking_type_1.copy()
        mo_1 = self.env['mrp.production'].create({
            'product_id': self.product1.id,
            'product_qty': 1,
            'picking_type_id': picking_type_1.id,
        })
        mo_2 = self.env['mrp.production'].create({
            'product_id': self.product1.id,
            'product_qty': 1,
            'picking_type_id': picking_type_2.id,
        })
        action = picking_type_1.get_action_picking_tree_ready_kanban()
        productions = self.env['mrp.production'].search(action['domain'])
        self.assertEqual(productions.ids, [mo_1.id])
        self.assertNotIn(mo_2.id, productions.ids)
