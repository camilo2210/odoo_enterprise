# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.tests import Form
from odoo.tests.common import HttpCase


class TestShopFloor(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Enables Work Order setting, and disables other settings.
        cls.env['res.config.settings'].create({'group_mrp_routings': True}).execute()

        # Create a test dedicated company.
        cls.company = cls.env['res.company'].create({'name': 'Test ShopFloor Company'})
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        # Create an employee for the user (it will be created for the test company.)
        cls.employee = cls.env['hr.employee'].create({'user_id': cls.env.user.id})

        group_lot = cls.env.ref('stock.group_production_lot')
        group_multi_loc = cls.env.ref('stock.group_stock_multi_locations')
        group_pack = cls.env.ref('stock.group_tracking_lot')
        group_uom = cls.env.ref('uom.group_uom')
        cls.env.user.write({'group_ids': [Command.unlink(group_lot.id)]})
        cls.env.user.write({'group_ids': [Command.unlink(group_multi_loc.id)]})
        cls.env.user.write({'group_ids': [Command.unlink(group_pack.id)]})
        # Explicitly remove the UoM group.
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_user.write({'implied_ids': [Command.unlink(group_uom.id)]})
        cls.env.user.write({'group_ids': [Command.unlink(group_uom.id)]})

        # Add some properties for commonly used in tests records.
        cls.warehouse = cls.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
            'code': 'TWH',
            'sequence': 5,
        })
        # Give WH's manufacturing operation a low sequence to prioritize it over other WH's ones.
        cls.warehouse.manu_type_id.sequence = 1
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.test_type_register_production = cls.env.ref('mrp_workorder.test_type_register_production')
        # Reset LN/SN sequence for the same reason.
        stock_lot_seq = cls.env['ir.sequence'].search([('code', '=', 'stock.lot.serial')])
        stock_lot_seq.number_next_actual = 1

        cls.shop_floor_user = cls.env['res.users'].create({
            'name': 'Test shopfloor user',
            'login': 'shop_floor_user',
            'group_ids': [
                Command.set(cls.env.ref('mrp.group_mrp_user').ids),
            ],
        })
        cls.shop_floor_user.action_create_employee()
        employees = cls.env['hr.employee'].create([{
            'name': name,
        } for name in ['Abbie Seedy', 'Billy Demo', 'Cory Corrinson']])
        employees[0].barcode = "659898105101"

        # Create basic data's to rely on
        (
            cls.final_product,
            cls.component_1,
            cls.component_2,
            cls.by_product,
            cls.product_1,
            cls.product_2,
        ) = cls.env['product.product'].create([
            {
                'name': name,
                'type': 'consu',
            } for name in (
                'Final Product',
                'Comp1',
                'Comp2',
                'By Product 1',
                'Product 1',
                'Product 2',
            )
        ])
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'Lovecenter',
            'barcode': 'OLDBARCODE',
        })
        cls.bom = cls.env['mrp.bom'].create({
            'product_id': cls.final_product.id,
            'product_tmpl_id': cls.final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Care', 'workcenter_id': cls.workcenter.id, 'time_cycle': 15, 'sequence': 1}),
                Command.create({'name': 'Communicate', 'workcenter_id': cls.workcenter.id, 'time_cycle': 20, 'sequence': 1}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': cls.component_1.id, 'product_qty': 1}),
                Command.create({'product_id': cls.component_2.id, 'product_qty': 2}),
            ],
            'byproduct_ids': [Command.create({'product_id': cls.by_product.id, 'product_qty': 1})],
        })
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')

    def setUp(self):
        super().setUp()
        self._reset_mo_sequence(warehouse=self.warehouse)

    # === UTIL METHODS ===#
    def _enable_settings(self, *args):
        fieldname_by_setting = {
            'by-product': 'group_mrp_byproducts',
            'locations': 'group_stock_multi_locations',
            'package': 'group_stock_tracking_lot',
            'tracking': 'group_stock_production_lot',
            'uom': 'group_uom',
            'workorder': 'group_mrp_routings',
        }
        create_vals = {}
        for setting in args:
            fieldname = fieldname_by_setting.get(setting)
            if fieldname:
                create_vals[fieldname] = True

        if create_vals:
            self.env['res.config.settings'].create(create_vals).execute()

    def _reset_mo_sequence(self, warehouse, next_number=1):
        """ Resets mo sequence to be sure we'll have the attended mo name."""
        warehouse.manu_type_id.sequence_id.number_next_actual = next_number

    # === TEST METHODS ===#
    def test_shop_floor(self):
        # Creates somme employees for test purpose.

        giraffe = self.env['product.product'].create({
            'name': 'Giraffe',
            'is_storable': True,
            'tracking': 'lot',
        })
        leg = self.env['product.product'].create({
            'name': 'Leg',
            'is_storable': True,
            'barcode': 'PRODUCT_LEG'
        })
        neck = self.env['product.product'].create({
            'name': 'Neck',
            'is_storable': True,
            'tracking': 'serial',
        })
        color = self.env['product.product'].create({
            'name': 'Color',
            'is_storable': True,
        })
        neck_sn_1, neck_sn_2 = self.env['stock.lot'].create([{
            'name': 'NE1',
            'product_id': neck.id,
        }, {
            'name': 'NE2',
            'product_id': neck.id,
        }])
        self.env['stock.quant']._update_available_quantity(leg, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(color, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(neck, self.stock_location, quantity=1, lot_id=neck_sn_1)
        self.env['stock.quant']._update_available_quantity(neck, self.stock_location, quantity=1, lot_id=neck_sn_2)
        savannah = self.env['mrp.workcenter'].create({
            'name': 'Savannah',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        jungle = self.env['mrp.workcenter'].create({'name': 'Jungle'})
        bom = self.env['mrp.bom'].create({
            'product_id': giraffe.id,
            'product_tmpl_id': giraffe.product_tmpl_id.id,
            'uom_id': giraffe.uom_id.id,
            'product_qty': 1.0,
            # Mark as done on work orders is blocked for continuous production for now.
            'continuous': True,
            'operation_ids': [
                Command.create({
                'name': 'Creation',
                'workcenter_id': savannah.id,
            }), Command.create({
                'name': 'Release',
                'workcenter_id': jungle.id,
            })],
            'bom_line_ids': [
                Command.create({'product_id': leg.id, 'product_qty': 4}),
                Command.create({'product_id': neck.id, 'product_qty': 1})
            ]
        })
        steps_common_values = {
            'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
            'product_ids': [Command.link(giraffe.id)],
            'operation_id': bom.operation_ids[0].id,
        }
        self.env['quality.point'].create([
            {
                **steps_common_values,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
                'sequence': 0,
            },
            {
                **steps_common_values,
                'title': 'Instructions',
                'test_type_id': self.env.ref('quality.test_type_instructions').id,
                'sequence': 1,
                'note': "Create this giraffe with a lot of care !",
            },
            {
                **steps_common_values,
                'title': 'Register legs',
                'bom_line_id': bom.bom_line_ids.filtered(lambda line: line.product_id == leg).id,
                'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
                'sequence': 2,
            },
            {
                **steps_common_values,
                'title': 'Register necks',
                'bom_line_id': bom.bom_line_ids.filtered(lambda line: line.product_id == neck).id,
                'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
                'sequence': 3,
            },
            {
                **steps_common_values,
                'title': 'Release',
                'test_type_id': self.env.ref('quality.test_type_instructions').id,
                'sequence': 4,
            },
        ])
        mo = self.env['mrp.production'].create({
            'product_id': giraffe.id,
            'product_qty': 2,
            'bom_id': bom.id,
        })
        mo.picking_type_id.prefill_shop_floor_lots = True
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        # Allow the user to create new products
        self.shop_floor_user.group_ids = [Command.link(self.ref('product.group_product_manager'))]
        self.start_tour('/odoo/shop-floor', "test_shop_floor", login='shop_floor_user')

        self.assertEqual(mo.move_finished_ids.quantity, 2)
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': leg.id, 'quantity': 10.0, 'state': 'done'},
            {'product_id': neck.id, 'quantity': 2.0, 'state': 'done'},
            {'product_id': color.id, 'quantity': 1.0, 'state': 'done'},
        ])
        self.assertRecordValues(mo.workorder_ids, [
            {'state': 'done', 'workcenter_id': savannah.id},
            {'state': 'done', 'workcenter_id': jungle.id},
        ])
        self.assertEqual(mo.lot_producing_ids, mo.move_finished_ids.move_line_ids.lot_id)
        self.assertEqual(mo.workorder_ids[0].qty_produced, 2)
        self.assertEqual(mo.workorder_ids[0].check_ids[2].move_id.quantity, 10)
        self.assertEqual(mo.workorder_ids[0].check_ids[3].move_id.quantity, 2)
        self.assertRecordValues(mo.workorder_ids[0].check_ids[3].move_id.lot_ids, [{'id': neck_sn_1}, {'id': neck_sn_2}])

    def test_shop_floor_disable_serial_create(self):
        """ This test ensures user can't create serial number in shopfloor if forbidden """
        self._enable_settings('tracking')
        self.warehouse.manu_type_id.use_create_components_lots = False

        self.product_1.is_storable = True
        self.product_2.write({
            'is_storable': True,
            'tracking': 'serial',
        })
        product_2_sn = self.env['stock.lot'].create({
            'name': 'P2S',
            'product_id': self.product_2.id,
        })
        self.env['stock.quant']._update_available_quantity(self.product_2, self.stock_location, quantity=1, lot_id=product_2_sn)
        mo = self.env['mrp.production'].create({
            'product_id': self.product_1.id,
            'product_qty': 1.0,
            'move_raw_ids': [Command.create({
                'product_id': self.product_2.id,
                'product_uom_qty': 1.0,
            })]
        })
        mo.action_confirm()

        with self.assertLogs(level="WARNING") as log_catcher:
            self.start_tour('/odoo/shop-floor', "test_shop_floor_disable_serial_create", login='shop_floor_user')
        self.assertEqual(len(log_catcher.output), 1, "Exactly one warning should be logged")
        self.assertIn(
            "You are not allowed to create or edit a lot or serial number",
            log_catcher.output[0],
            "The logged warning should warn about creating serial numbers for components",
        )

    def test_shop_floor_auto_select_workcenter(self):
        """ This test ensures the right work center is selected when Shop Floor is opened."""
        # Create some products.
        product_final = self.env['product.product'].create({
            'name': 'Pizza',
            'is_storable': True,
        })
        product_comp1 = self.env['product.product'].create({
            'name': 'Pizza dough',
            'is_storable': True,
        })
        product_comp2 = self.env['product.product'].create({
            'name': 'Tomato sauce',
            'is_storable': True,
        })
        # Adds some quantity in stock.
        self.env['stock.quant']._update_available_quantity(product_comp1, self.stock_location, quantity=999)
        self.env['stock.quant']._update_available_quantity(product_comp2, self.stock_location, quantity=999)
        # Create three workcenters.
        wc1, wc2 = self.env['mrp.workcenter'].create([{
            'name': f'Preparation Table {i}',
        } for i in (1, 2)])
        wc1.alternative_workcenter_ids = wc2
        wc2.alternative_workcenter_ids = wc1
        wc3 = self.env['mrp.workcenter'].create({'name': 'Furnace'})
        # Create a BoM.
        bom = self.env['mrp.bom'].create({
            'product_id': product_final.id,
            'product_tmpl_id': product_final.product_tmpl_id.id,
            'uom_id': product_final.uom_id.id,
            'product_qty': 1.0,
            'continuous': True,
            'operation_ids': [
                Command.create({
                'name': 'Prepare the pizza 🤌',
                'workcenter_id': wc1.id,
            }), Command.create({
                'name': 'Bake it!',
                'workcenter_id': wc3.id,
            })],
            'bom_line_ids': [
                Command.create({'product_id': product_comp1.id, 'product_qty': 1}),
                Command.create({'product_id': product_comp2.id, 'product_qty': 1})
            ]
        })
        # Create two Manufacturing Orders.
        all_mo = self.env['mrp.production'].create([{
            'product_id': product_final.id,
            'product_qty': qty,
            'bom_id': bom.id,
        } for qty in (6, 4)])
        all_mo.action_confirm()
        all_mo.action_assign()
        all_mo.button_plan()
        # Mark as done the 2th MO 1st WO.
        all_mo[1].workorder_ids[0].button_start()
        all_mo[1].workorder_ids[0].action_mark_as_done()
        all_mo[0].workorder_ids[1].barcode = "bake it lovely"
        self.start_tour("/odoo/shop-floor", "test_shop_floor_auto_select_workcenter", login='shop_floor_user')

    def test_shop_floor_workcenter_barcode_refresh(self):
        """ Ensures a work center's barcode used to select it in the Shop Floor
        is refreshed on (re)load, even if a stale value was cached in the
        browser's local storage. """
        self.env['res.users'].create({
            'name': 'Test MRP Manager',
            'login': 'mrp_manager',
            'group_ids': [
                Command.set(self.env.ref('mrp.group_mrp_manager').ids),
            ],
        })
        self.start_tour('/odoo/shop-floor', 'test_shop_floor_workcenter_barcode_refresh', login='mrp_manager')

    def test_shop_floor_catalog_add_component_in_two_steps(self):
        """ Ensures when a component is added through the Shop Floor catalog,
        the Pick Component operation is correctly created/updated."""
        # Set the manufacture in 2 steps.
        self.warehouse.manufacture_steps = 'pbm'
        # Create a product with a BoM and two components.
        # Create some products.
        product_final = self.env['product.product'].create({
            'name': 'Pot',
            'is_storable': True,
        })
        product_comp1, product_comp2 = self.env['product.product'].create([{
            'name': 'C1 - Earthenware Clay',
            'is_storable': True,
        }, {
            'name': 'C2 - Stoneware Clay',
            'is_storable': True,
        }])
        bom = self.env['mrp.bom'].create({
            'product_id': product_final.id,
            'product_tmpl_id': product_final.product_tmpl_id.id,
            'uom_id': product_final.uom_id.id,
            'product_qty': 1.0,
            'bom_line_ids': [
                Command.create({'product_id': product_comp1.id, 'product_qty': 1}),
            ]
        })
        # Adds some quantity in stock.
        self.env['stock.quant']._update_available_quantity(product_comp1, self.stock_location, quantity=999)
        self.env['stock.quant']._update_available_quantity(product_comp2, self.stock_location, quantity=999)
        # Create a Manufacturing Order.
        mo = self.env['mrp.production'].create({
            'product_id': product_final.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        # Validate the MO's Pick Component.
        self.assertEqual(len(mo.picking_ids), 1)
        mo.picking_ids.button_validate()
        # Simulate "Add Component" from the Shop Floor.
        kwargs = {'from_shop_floor': True}
        mo._update_order_line_info(product_comp2, 1, product_comp2.uom_id, child_field='move_raw_ids', **kwargs)
        self.assertEqual(len(mo.picking_ids), 2, "A second picking should have been created for the MO")
        self.assertEqual(mo.components_availability_state, 'available', "MO should still be ready nevertheless")
        second_picking = mo.picking_ids.filtered(lambda p: p.state == 'assigned')
        self.assertRecordValues(second_picking.move_ids, [
            {'product_id': product_comp2.id, 'product_uom_qty': 1, 'picked': False},
        ])
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': product_comp1.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
            {'product_id': product_comp2.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
        ])
        # Simulate adding more quantity from the Shop Floor.
        mo._update_order_line_info(product_comp2, 2, product_comp2.uom_id, child_field='move_raw_ids', **kwargs)
        self.assertEqual(len(mo.picking_ids), 2, "No other picking should have been created")
        self.assertEqual(mo.components_availability_state, 'available', "MO should still be ready")
        self.assertRecordValues(second_picking.move_ids, [
            {'product_id': product_comp2.id, 'product_uom_qty': 2, 'picked': False},
        ])
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': product_comp1.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
            {'product_id': product_comp2.id, 'product_uom_qty': 2, 'quantity': 2, 'picked': False},
        ])
        # starts the MO and simulate adding more quantity from the Shop Floor.
        mo.action_start()
        self.assertEqual(mo.state, 'progress')
        mo._update_order_line_info(product_comp2, 3, product_comp2.uom_id, child_field='move_raw_ids', **kwargs)
        self.assertEqual(len(mo.picking_ids), 2, "No other picking should have been created")
        self.assertEqual(mo.components_availability_state, 'available', "MO should still be ready")
        self.assertRecordValues(second_picking.move_ids, [
            {'product_id': product_comp2.id, 'product_uom_qty': 3, 'picked': False},
        ])
        self.assertRecordValues(mo.move_raw_ids, [
            {'product_id': product_comp1.id, 'product_uom_qty': 1, 'quantity': 1, 'picked': False},
            {'product_id': product_comp2.id, 'product_uom_qty': 3, 'quantity': 3, 'picked': False},
        ])

    def test_shop_floor_my_wo_filter_with_pin_user(self):
        """Checks the shown Work Orders (in "My WO" section) are correctly
        refreshed when selected user uses a PIN code."""
        # Create two employees (one with no PIN code and one with a PIN code.)
        self.env['hr.employee'].sudo().create([
            {'name': 'John Snow'},
            {'name': 'Queen Elsa', 'pin': '41213'},
        ])
        # Create some products and add enough quantity in stock for the components.
        final_product, comp_1, comp_2 = self.env['product.product'].create([{
            'name': name,
            'is_storable': True,
        } for name in ['Snowman', 'Snowball', 'Carrot']])
        self.env['stock.quant']._update_available_quantity(comp_1, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(comp_2, self.stock_location, quantity=100)
        # Configure all the needs to create a MO with at least one WO.
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Winter\'s Workshop',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        bom = self.env['mrp.bom'].create({
            'product_id': final_product.id,
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'uom_id': final_product.uom_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({
                    'name': 'Build the Snowman',
                    'workcenter_id': workcenter.id,
                }),
            ],
            'bom_line_ids': [
                Command.create({'product_id': comp_1.id, 'product_qty': 3}),
                Command.create({'product_id': comp_2.id, 'product_qty': 1}),
            ],
        })
        # Mark the components as to consume in the operation so they appear in the Shop Floor.
        bom.bom_line_ids.operation_id = bom.operation_ids.id
        # Create, confirm and plan two MO.
        all_mo = self.env['mrp.production'].create([{
            'product_id': final_product.id,
            'product_qty': qty,
            'bom_id': bom.id,
        } for qty in [3, 5]])
        all_mo.action_confirm()
        all_mo.action_assign()
        all_mo.button_plan()
        self.start_tour('/odoo/shop-floor', 'test_shop_floor_my_wo_filter_with_pin_user', login='shop_floor_user')

    def test_generate_serials_in_shopfloor(self):
        """ Ensure we can produce a MO with By-Product even if it's tracked by SN,
        then check the By-Product comes and goes in the right locations."""
        self._enable_settings('tracking', 'by-product')
        component1 = self.env['product.product'].create({
            'name': 'comp1',
            'is_storable': True,
        })
        component2 = self.env['product.product'].create({
            'name': 'comp2',
            'is_storable': True,
        })
        finished = self.env['product.product'].create({
            'name': 'finish',
            'is_storable': True,
        })
        byproduct = self.env['product.product'].create({
            'name': 'byprod',
            'is_storable': True,
            'tracking': 'serial',
        })
        self.env['stock.quant']._update_available_quantity(component1, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(component2, self.stock_location, quantity=100)
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Assemble', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component1.id, 'product_qty': 1}),
                Command.create({'product_id': component2.id, 'product_qty': 1}),
            ],
            'byproduct_ids': [
                Command.create({'product_id': byproduct.id, 'product_qty': 1}),
            ]
        })
        bom.byproduct_ids[0].operation_id = bom.operation_ids[0].id
        self.by_product.write({
            'is_storable': True,
            'tracking': 'serial'
        })
        mo = self.env['mrp.production'].create({
            'product_id': finished.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.move_byproduct_ids = [Command.create({
                'product_id': self.by_product.id,
                'product_uom_qty': 1
        })]
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        action = self.env["ir.actions.actions"]._for_xml_id("mrp_workorder.action_mrp_display")
        url = f"/odoo/action-{action['id']}"
        self.start_tour(url, "test_generate_serials_in_shopfloor", login='shop_floor_user')
        self.assertRecordValues(mo.move_byproduct_ids,
            [{
                'product_id': byproduct.id,
                'location_id': mo.production_location_id.id,
                'location_dest_id': self.stock_location.id
            },
            {
                'product_id': self.by_product.id,
                'location_id': mo.production_location_id.id,
                'location_dest_id': self.stock_location.id
            }
            ])
        self.assertRecordValues(mo.move_byproduct_ids,
            [{
                'product_id': byproduct.id,
                'location_id': mo.production_location_id.id,
                'location_dest_id': self.stock_location.id
            },
            {
                'product_id': self.by_product.id,
                'location_id': mo.production_location_id.id,
                'location_dest_id': self.stock_location.id
            }
            ])
        self.assertRecordValues(mo.move_byproduct_ids.lot_ids, [{'name': '00001'}, {'name': '00002'}])

    def test_byproduct_empty_bom_action_add_from_quant(self):
        """
        Ensure a manually added tracked by-product on an MO with an empty BOM
        can prefill lots from a quant and complete successfully when
        `prefill_shop_floor_lots` is enabled.
        """
        prod_location = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', '=', self.company.id)], limit=1)
        self._enable_settings('tracking', 'by-product')
        self.product_1.is_storable = True
        self.by_product.write({
            'is_storable': True,
            'tracking': 'serial',
        })

        lot = self.env['stock.lot'].create({
            'name': 'LOT-BYPRODUCT-001',
            'product_id': self.by_product.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant']._update_available_quantity(
            self.by_product,
            prod_location,
            1,
            lot_id=lot,
        )

        mo = self.env['mrp.production'].create({
            'product_id': self.product_1.id,
            'product_qty': 1.0,
        })
        mo.picking_type_id.prefill_shop_floor_lots = True
        mo.move_byproduct_ids = [Command.create({
            'product_id': self.by_product.id,
            'product_uom_qty': 1.0,
        })]
        mo.action_confirm()
        mo.move_byproduct_ids.action_add_from_quant(self.by_product.stock_quant_ids.id)

        mo.button_mark_done()
        self.assertEqual(mo.state, 'done')

    def test_byproduct_serial_with_prefill_lots(self):
        """ When prefill_shop_floor_lots is enabled, by-products tracked by serial
        should not show pre-filled empty lines in shopfloor. Only lines explicitly
        registered by the user (picked) should be visible."""
        self._enable_settings('tracking', 'by-product')
        component1, component2, finished, byproduct = self.env['product.product'].create([{
            'name': name,
            'is_storable': True,
        } for name in ('comp1', 'comp2', 'finish', 'byprod')])
        byproduct.tracking = 'serial'
        self.env['stock.quant']._update_available_quantity(component1, self.stock_location, quantity=100)
        self.env['stock.quant']._update_available_quantity(component2, self.stock_location, quantity=100)
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Assemble', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component1.id, 'product_qty': 1}),
                Command.create({'product_id': component2.id, 'product_qty': 1}),
            ],
            'byproduct_ids': [
                Command.create({'product_id': byproduct.id, 'product_qty': 1}),
            ]
        })
        bom.byproduct_ids[0].operation_id = bom.operation_ids[0].id
        mo = self.env['mrp.production'].create({
            'product_id': finished.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.picking_type_id.prefill_shop_floor_lots = True
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        self.start_tour('/odoo/shop-floor', "test_byproduct_serial_with_prefill_lots", login='shop_floor_user')
        self.assertEqual(mo.move_byproduct_ids.lot_ids.name, "00001")
        self.assertEqual(len(mo.move_byproduct_ids.move_line_ids), 1,
            "By-product should have exactly one move line (the registered serial), no extra empty line")

    def test_partial_backorder_with_multiple_operations(self):
        """
        Create an MO for 10 units and 3 operations: op1, op2, op3. Process:
        - 10 units in op1
        - 7 units in op2
        - 5 units in op3
        Validate the MO for these 5 units and create a backorder. Check that each operation of the
        backorder displays the appropriate remaining quantity in the backend and in the shopfloor:
        - op1 shall be cancelled
        - op2 shall be processed for 3 units
        - op3 shall be processed for 5 units

        Additionaly, verify that the filters are not erased when marking an operation as done.
        """
        finished = self.env['product.product'].create({
            'name': 'finish',
            'is_storable': True,
        })
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'continuous': True,
            'operation_ids': [
                Command.create({'name': 'op1', 'workcenter_id': workcenter.id}),
                Command.create({'name': 'op2', 'workcenter_id': workcenter.id}),
                Command.create({'name': 'op3', 'workcenter_id': workcenter.id}),
            ],
        })

        # Cancel previous MOs and create a new one
        self.env['mrp.production'].search([('state', 'not in', ('cancel', 'done'))]).action_cancel()
        mo = self.env['mrp.production'].create({
            'name': 'MOBACK',
            'product_id': finished.id,
            'product_qty': 10,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        # wo_1 completely finished, wo_2 and wo_3 partially finished
        for wo, qty in zip(mo.workorder_ids, (10, 7, 5)):
            wo.button_start()
            with Form(mo) as fmo:
                fmo.qty_producing = qty
            wo.button_finish()

        # Create a backorder
        action = mo.button_mark_done()
        backorder = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder.save().action_backorder()
        mo_backorder = mo.production_group_id.production_ids[-1]
        mo_backorder.button_plan()

        # Sanity check
        self.assertEqual(mo_backorder.workorder_ids[0].state, 'cancel')
        self.assertEqual(mo_backorder.workorder_ids[1].state, 'ready')

        self.start_tour("odoo/manufacturing", "test_partial_backorder_with_multiple_operations", login='shop_floor_user')

    def test_change_qty_produced(self):
        """
            Check that component quantity matches the quantity produced set in the shop
            floor register production change to the quantity produced
            Example:
                move.uom_unit = 2.
                bom.final_quantity = 1
                MO.qty_producing = 5 -> should consume 10 components for move_raw.
                Confirm MO and update MO.qty_producing = 3
                Finish the workorder, then it should consume 6 components for move_raw.
            The above behaviour should be occur on the MO form and shop floor.
        """
        bom = self.env['mrp.bom'].create({
            'product_id': self.final_product.id,
            'product_tmpl_id': self.final_product.product_tmpl_id.id,
            'uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': self.workcenter.id, 'time_cycle': 12, 'sequence': 1}),
                Command.create({'name': 'OP2', 'workcenter_id': self.workcenter.id, 'time_cycle': 18, 'sequence': 2})
            ],
            'bom_line_ids': [
                Command.create({
                    'product_id': self.component_1.id,
                    'product_qty': 1.0
                }),
                Command.create({
                    'product_id': self.component_2.id,
                    'product_qty': 2.0
                }),
            ]
        })

        # Link components to their respective operations
        bom.bom_line_ids[0].operation_id = bom.operation_ids[0]
        bom.bom_line_ids[1].operation_id = bom.operation_ids[1]

        # Create a step to register production
        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(self.final_product.id)],
                'operation_id': bom.operation_ids[1].id,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = bom
        mo_form.product_qty = 5
        mo = mo_form.save()
        mo.action_confirm()

        wo = mo.workorder_ids[0]
        wo.button_start()
        wo.button_finish()
        self.start_tour("/odoo/shop-floor", "test_change_qty_produced", login='shop_floor_user')
        self.assertEqual(mo.qty_producing, 3)
        for move in mo.move_raw_ids:
            if move.product_id.id == self.component_1.id:
                self.assertEqual(move.quantity, 5)
                self.assertTrue(move.picked)
            if move.product_id.id == self.component_2.id:
                self.assertEqual(move.quantity, 6)
                self.assertTrue(move.picked)

    def test_continuous_bom_change_qty_produced(self):
        """
            Check that for continuous BOMs, changing the quantity in the shop
            floor register production does NOT update the MO's qty_producing unless its
            the last workorder in shopfloor.
        """
        continuous_bom = self.env['mrp.bom'].create({
            'product_id': self.final_product.id,
            'product_tmpl_id': self.final_product.product_tmpl_id.id,
            'uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'continuous': True,
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': self.workcenter.id, 'time_cycle': 12, 'sequence': 1}),
                Command.create({'name': 'OP2', 'workcenter_id': self.workcenter.id, 'time_cycle': 18, 'sequence': 2})
            ],
            'bom_line_ids': [
                Command.create({'product_id': self.component_1.id, 'product_qty': 1.0}),
                Command.create({'product_id': self.component_2.id, 'product_qty': 2.0}),
            ]
        })

        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(self.final_product.id)],
                'operation_id': continuous_bom.operation_ids[1].id,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = continuous_bom
        mo_form.product_qty = 5
        mo = mo_form.save()
        mo.action_confirm()

        wo = mo.workorder_ids[0]
        wo.button_start()
        wo.button_finish()
        self.assertEqual(mo.qty_producing, 0)
        self.start_tour("/odoo/shop-floor", "test_continuous_bom_change_qty_produced", login='shop_floor_user')
        self.assertEqual(mo.qty_producing, 3)
        for move in mo.move_raw_ids:
            if move.product_id.id == self.component_1.id:
                self.assertEqual(move.quantity, 3)
            if move.product_id.id == self.component_2.id:
                self.assertEqual(move.quantity, 6)

    def test_operator_assigned_to_all_work_orders(self):
        """
        Check that, if a custom operator is selected in the side panel, all work orders
        completed via Shop Floor are assigned to that operator.
        """
        employee = self.env['hr.employee'].sudo().create([{'name': 'Anita Olivier'}])
        product = self.env['product.product'].create({'name': 'P', 'is_storable': True})
        workcenter = self.env['mrp.workcenter'].create({'name': 'Workcenter1'})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1.0,
            'continuous': True,
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': workcenter.id}),
                Command.create({'name': 'OP2', 'workcenter_id': workcenter.id}),
            ],
        })
        mo = self.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()

        self.start_tour('/odoo/shop-floor', 'test_operator_assigned_to_all_work_orders', login='shop_floor_user')

        logs = mo.workorder_ids.time_ids
        self.assertEqual(len(logs), 2, 'Both operations should be logged.')
        self.assertEqual(logs[0].employee_id, employee, 'OP1 should be assigned to "Anita Olivier"')
        self.assertEqual(
            logs[0].description, 'Time Tracking: Anita Olivier',
            'The description of OP1 should mention "Anita Olivier"'
        )
        self.assertEqual(logs[1].employee_id, employee, 'OP2 should be assigned to "Anita Olivier"')
        self.assertEqual(
            logs[1].description, 'Time Tracking: Anita Olivier',
            'The description of OP2 should mention "Anita Olivier"'
        )

    def test_automatic_backorder_no_redirect(self):
        """
        Test that the backorder is created without redirecting to the
        production form on shopfloor. This is the case when the backorder
        is created automatically by the system on shopfloor.
        Also check that the production can be closed if there is nothing to backorder.
        """
        self.warehouse.manu_type_id.create_backorder = 'always'
        final_product, component = self.env['product.product'].create([
            {
                'name': 'Product',
                'type': 'consu',
                'is_storable': True,
            },
            {
                'name': 'Component1',
                'type': 'consu',
                'is_storable': True,
            },
        ])
        self.env['stock.quant']._update_available_quantity(product_id=component, location_id=self.stock_location, quantity=100)
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Workcenter1',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Operation1', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1}),
            ]
        })
        # Create a step to register production.
        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(final_product.id)],
                'operation_id': bom.operation_ids[0].id,
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])
        mo = self.env['mrp.production'].create({
                'name': "MOBACK",
                'product_id': final_product.id,
                'product_qty': 2,
                'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        self.start_tour("/odoo/shop-floor", "test_automatic_backorder_no_redirect", login='shop_floor_user')
        self.assertRecordValues(mo.production_group_id.production_ids.sorted('name'), [
            {'name': 'MOBACK-001', 'state': 'done'},
            {'name': 'MOBACK-002', 'state': 'done'},
        ])

    def test_shop_floor_access(self):
        mrp_partner = self.env['res.partner'].create({'name': 'mrp_user'})
        self.env['res.users'].sudo().create({
            'login': 'mrp_user',
            'partner_id': mrp_partner.id,
            'group_ids': [Command.set(self.env.ref('mrp.group_mrp_routings').ids)],
        })
        self.env['mrp.workcenter'].create({'name': 'Workcenter1'})
        self.start_tour('/odoo', 'test_shop_floor_access', login='shop_floor_user')

    def test_set_qty_producing(self):
        component, final_product = self.env['product.product'].create([{
            'name': 'component',
            'is_storable': True,
        }, {
            'name': 'final product',
            'is_storable': True,
            'tracking': 'serial',
        }])
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'Assembly Line',
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'Operation1', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1}),
            ]
        })
        self.env['quality.point'].create([{
                'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
                'product_ids': [Command.link(final_product.id)],
                'title': 'Register Production',
                'test_type_id': self.test_type_register_production.id,
        }])
        mo = self.env['mrp.production'].create({
            'product_id': final_product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })

        mo.action_confirm()
        wo = mo.workorder_ids[0]
        Form.from_action(self.env, wo.action_add_step()).save().add_check_in_chain()
        wo.set_qty_producing()

        first_check = wo.check_ids[0]
        last_check = wo.check_ids[1]
        new_check = last_check.copy()
        wo.set_qty_producing()

        self.assertEqual(last_check.next_check_id, new_check)
        self.assertEqual(new_check.previous_check_id, last_check)
        self.assertEqual(new_check.next_check_id, first_check)
        self.assertEqual(first_check.previous_check_id, new_check)
        self.assertFalse(first_check.next_check_id)
        self.assertEqual(wo.current_quality_check_id, first_check)
        self.assertFalse(wo.allow_producing_quantity_change)

    def test_shop_floor_unsynced_bom(self):
        """ Check that when a component that has been removed from a BoM with
            a not done MO, it still shows the component in the shop floor for
            that MO.
        """
        demo = self.env['product.product'].create({'name': 'DEMO'})
        comp1, comp2 = self.env['product.product'].create([{
            'name': name,
            'is_storable': True
        } for name in ['COMP1', 'COMP2']])
        work_center = self.env['mrp.workcenter'].create({"name": "WorkCenter", "time_start": 11})
        bom = self.env['mrp.bom'].create({
            'product_id': demo.id,
            'product_tmpl_id': demo.product_tmpl_id.id,
            'uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'continuous': True,
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': work_center.id, 'time_cycle': 12, 'sequence': 1}),
                Command.create({'name': 'OP2', 'workcenter_id': work_center.id, 'time_cycle': 18, 'sequence': 2})
            ]
        })
        # Create a step to register production.
        self.env['quality.point'].create([{
            'picking_type_ids': [Command.link(self.warehouse.manu_type_id.id)],
            'product_ids': [Command.link(demo.id)],
            'operation_id': bom.operation_ids[1].id,
            'title': 'Register Production',
            'test_type_id': self.test_type_register_production.id,
        }])
        self.env['mrp.bom.line'].create([
            {
                'product_id': comp.id,
                'product_qty': qty,
                'bom_id': bom.id,
                'operation_id': operation.id,
            } for comp, qty, operation in zip([comp1, comp2], [1.0, 2.0], bom.operation_ids)
        ])
        self.env['stock.quant'].create([
            {
                'location_id': self.stock_location.id,
                'product_id': comp.id,
                'inventory_quantity': 20,
            } for comp in [comp1, comp2]
        ]).action_apply_inventory()

        mo = self.env['mrp.production'].create({
            'product_id': demo.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        mo.action_assign()
        mo.button_plan()
        # Remove one component from the BoM, so that the MO and BoM are unsynced
        bom.bom_line_ids[0].unlink()

        self.start_tour("/odoo/shop-floor", "test_shop_floor_unsynced_bom", login='shop_floor_user')

        self.assertEqual(mo.qty_producing, 1)
        for move in mo.move_raw_ids:
            if move.product_id.id == comp1.id:
                self.assertEqual(move.quantity, 1)
                self.assertTrue(move.picked)
            if move.product_id.id == comp2.id:
                self.assertEqual(move.quantity, 2)
                self.assertTrue(move.picked)

    def test_product_consumption(self):
        """ Test that we generate the correct move when completing from the shopfloor
        a MO with component consumption. The component is tracked by lot, and use kg
        as its default UoM.
        BoM: component 50g => product 1 Unit
        """
        # user need to be in the production lot group to be able to see the lot id in the quant selection view.
        self.shop_floor_user.write({'group_ids': [Command.link(self.ref('stock.group_production_lot'))]})

        warehouse2 = self.env['stock.warehouse'].create({
            'name': 'Test Warehouse 2',
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
            'code': 'TWH2',
            'sequence': 6,
        })
        workcenter = self.env['mrp.workcenter'].create({'name': 'Workcenter1'})
        component, product = self.env["product.product"].create([
                {
                    "name": "component",
                    "is_storable": True,
                    "tracking": "lot",
                    "uom_id": self.ref("uom.product_uom_kgm"),
                },
                {
                    "name": "product",
                    "is_storable": True,
                },
        ])
        bom = self.env['mrp.bom'].create({
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'operation_ids': [
                Command.create({'name': 'consumption', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({
                    'product_id': component.id,
                    'product_qty': 50,
                    'uom_id': self.ref('uom.product_uom_gram'),
                }),
            ],
        })
        lot_1, lot_2 = self.env['stock.lot'].create([
            {'name': 'Lot 1', 'product_id': component.id},
            {'name': 'Lot 2', 'product_id': component.id},
        ])
        bom.bom_line_ids.operation_id = bom.operation_ids.id
        self.env['stock.quant']._update_available_quantity(component, self.stock_location, quantity=100, lot_id=lot_1)
        self.env['stock.quant']._update_available_quantity(component, self.stock_location, quantity=100, lot_id=lot_2)
        self.env['stock.quant']._update_available_quantity(component, warehouse2.lot_stock_id, quantity=100, lot_id=lot_2)
        mo = self.env['mrp.production'].create({
            'product_id': product.id,
            'bom_id': bom.id,
        })
        mo.action_confirm()
        self.start_tour('/odoo/shop-floor', 'test_product_consumption', login='shop_floor_user')

        self.assertRecordValues(mo.move_raw_ids, [
            {
                'product_id': component.id,
                'product_qty': 0.05,
                'product_uom_qty': 50.0,
                'lot_ids': lot_1.ids,
                'uom_id': self.ref('uom.product_uom_gram'),
            },
        ])

    def test_add_component_from_shop_floor(self):
        """
        Check that components added to a WO from the shopfloor are visible
        on both the WO and the MO and that, in multi step manufacturing,
        the associated tranfers are generated accordingly.
        """
        self.warehouse.manufacture_steps = "pbm"
        # Put products in stock to be added to the MO/WO
        (self.product_1 | self.product_2).write({
            'is_favorite': True,
            'is_storable': True,
        })
        self.env['stock.quant']._update_available_quantity(self.product_1, self.warehouse.lot_stock_id, quantity=10.0)
        self.env['stock.quant']._update_available_quantity(self.product_2, self.warehouse.lot_stock_id, quantity=10.0)
        mo = self.env['mrp.production'].create({
            'name': 'First Love',
            'product_id': self.final_product.id,
            'product_qty': 1,
            'bom_id': self.bom.id,
            'warehouse_id': self.warehouse.id,
        })
        # Tests workorders that are not linked to the bom by removing the link between these
        mo.workorder_ids[0].operation_id = False
        mo.action_confirm()
        pick = mo.picking_ids
        self.assertEqual(pick.picking_type_id, self.warehouse.pbm_type_id)
        pick.button_validate()
        self.start_tour("/odoo/shop-floor", "test_add_component_from_shop_floor", login='shop_floor_user')
        self.assertEqual(mo.workorder_ids[0], mo.move_raw_ids.filtered(lambda m: m.product_id == self.product_2).workorder_id)
        new_pick = mo.picking_ids - pick
        self.assertEqual(new_pick.picking_type_id, self.warehouse.pbm_type_id)
        self.assertRecordValues(new_pick.move_ids, [
            {'quantity': 2.0, 'product_id': self.product_1.id},
            {'quantity': 1.0, 'product_id': self.product_2.id},
        ])

    def test_scrap_component_from_shopfloor(self):
        """This test ensures that a component can be successfully scrapped from a
        specific work center via the Shop Floor interface and that a success
        notification is displayed.
        """
        workcenter = self.env['mrp.workcenter'].create({'name': 'Workcenter'})
        component, final_product = self.env['product.product'].create([{
            'name': name,
            'is_storable': True,
        } for name in ['component', 'Final Product']])
        self.env['stock.quant']._update_available_quantity(component, self.stock_location, quantity=10)

        bom = self.env['mrp.bom'].create({
            'product_id': final_product.id,
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_qty': 1,
            'operation_ids': [
                Command.create({'name': 'Component Consumption', 'workcenter_id': workcenter.id}),
            ],
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 5}),
            ],
        })
        mo = self.env['mrp.production'].create({
            'product_id': final_product.id,
            'bom_id': bom.id,
        })
        mo.action_confirm()

        self.start_tour('/odoo/shop-floor', 'test_scrap_component_from_shopfloor', login='shop_floor_user')
        self.assertEqual(mo.scrap_count, 1, 'One scrap order should be created.')

    def test_barcode_scan_returns_stock_quant_not_vendor_quant(self):
        """
        Scanning a serial barcode must return the WH/Stock quant even when a
        Partners/Vendors quant with the same serial number exists and has a
        lower database ID (i.e. was inserted first).
        """
        self._enable_settings('tracking')
        product_serial = self.env['product.product'].create({
            'name': 'Hand Piece',
            'is_storable': True,
            'tracking': 'serial',
        })
        product_finished = self.env['product.product'].create({
            'name': 'Final Product',
            'is_storable': True,
        })
        serial_lot = self.env['stock.lot'].create({
            'name': 'SN-TEST-001',
            'product_id': product_serial.id,
            'company_id': self.env.company.id,
        })
        workcenter = self.env['mrp.workcenter'].create({'name': 'Assembly'})
        bom = self.env['mrp.bom'].create({
            'product_id': product_finished.id,
            'product_tmpl_id': product_finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [Command.create({'name': 'Assembly', 'workcenter_id': workcenter.id})],
            'bom_line_ids': [Command.create({'product_id': product_serial.id, 'product_qty': 1})],
        })
        bom.bom_line_ids.operation_id = bom.operation_ids.id
        vendor_location = self.env.ref('stock.stock_location_suppliers')
        self.env['stock.quant'].create({
            'product_id': product_serial.id,
            'location_id': vendor_location.id,
            'lot_id': serial_lot.id,
            'quantity': -1,
        })
        self.env['stock.quant']._update_available_quantity(
            product_serial, self.stock_location, 1, lot_id=serial_lot
        )

        mo = self.env['mrp.production'].create({
            'product_id': product_finished.id,
            'bom_id': bom.id,
            'product_qty': 1,
        })
        mo.action_confirm()
        self.start_tour('/odoo/shop-floor', 'test_barcode_scan_returns_stock_quant_not_vendor_quant', login='shop_floor_user')
        self.assertEqual(mo.move_raw_ids.move_line_ids.location_id.id, self.stock_location.id)

    def test_shop_floor_workorders_sorting(self):
        product_final = self.env['product.product'].create({'name': 'Final Sort', 'is_storable': True, 'company_id': self.company.id})
        product_comp = self.env['product.product'].create({'name': 'Comp Sort', 'is_storable': True, 'company_id': self.company.id})
        self.env['stock.quant'].create({
            'product_id': product_comp.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'quantity': 100,
        })
        wc = self.env['mrp.workcenter'].create({'name': 'WC Sorting', 'company_id': self.company.id})
        bom = self.env['mrp.bom'].create({
            'product_id': product_final.id,
            'product_tmpl_id': product_final.product_tmpl_id.id,
            'uom_id': product_final.uom_id.id,
            'product_qty': 1.0,
            'operation_ids': [Command.create({'name': 'Op1', 'workcenter_id': wc.id})],
            'bom_line_ids': [Command.create({'product_id': product_comp.id, 'product_qty': 1})]
        })
        mo_unplanned = self.env['mrp.production'].create({'product_id': product_final.id, 'product_qty': 1, 'bom_id': bom.id})
        mo_planned = self.env['mrp.production'].create({'product_id': product_final.id, 'product_qty': 1, 'bom_id': bom.id})
        (mo_unplanned | mo_planned).action_confirm()
        (mo_unplanned | mo_planned).action_assign()
        # update name so JS tour can identify them easily
        mo_unplanned.name = "MO_UNPLANNED"
        mo_planned.name = "MO_PLANNED"

        # Explicitly set date_start to guarantee the test condition
        mo_unplanned.workorder_ids.write({'date_start': False})
        mo_planned.workorder_ids.write({'date_start': '2025-01-01 10:00:00'})

        self.assertEqual(mo_unplanned.workorder_ids.state, 'ready')
        self.assertEqual(mo_planned.workorder_ids.state, 'ready')

        self.start_tour("/odoo/shop-floor", "test_shop_floor_workorders_sorting", login='shop_floor_user')
