# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import product

from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import expr_eval
from odoo import Command


class TestQuality(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        grp_workorder = cls.env.ref('mrp.group_mrp_routings')
        cls.env.user.write({'group_ids': [(4, grp_workorder.id)]})

        cls.product_1 = cls.env['product.product'].create({'name': 'Table'})
        cls.product_2 = cls.env['product.product'].create({'name': 'Table top'})
        cls.product_3 = cls.env['product.product'].create({'name': 'Table leg'})
        cls.workcenter_1 = cls.env['mrp.workcenter'].create({
            'name': 'Test Workcenter',
            'time_start': 10,
            'time_stop': 5,
            'time_efficiency': 80,
        })
        cls.bom = cls.env['mrp.bom'].create({
            'product_id': cls.product_1.id,
            'product_tmpl_id': cls.product_1.product_tmpl_id.id,
            'uom_id': cls.product_1.uom_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                (0, 0, {'name': 'Assembly', 'workcenter_id': cls.workcenter_1.id, 'time_cycle': 15, 'sequence': 1}),
            ],
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': cls.product_2.id, 'product_qty': 1}),
                (0, 0, {'product_id': cls.product_3.id, 'product_qty': 4})
            ]
        })

    def test_quality_point_onchange(self):
        quality_point_form = Form(self.env['quality.point'].with_context(default_product_ids=[self.product_2.id]))
        # Form should keep the default products set
        self.assertEqual(len(quality_point_form.product_ids), 1)
        self.assertEqual(quality_point_form.product_ids[0].id, self.product_2.id)
        # <field name="operation_id" invisible="not is_workorder_step"/>
        # @api.depends('operation_id', 'picking_type_ids')
        # def _compute_is_workorder_step(self):
        #     for quality_point in self:
        #         quality_point.is_workorder_step = quality_point.operation_id or quality_point.picking_type_ids and\
        #             all(pt.code == 'mrp_operation' for pt in quality_point.picking_type_ids)
        quality_point_form.picking_type_ids.add(
            self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1)
        )
        # Select a workorder operation
        quality_point_form.operation_id = self.bom.operation_ids[0]
        # Product should be replaced by the product linked to the bom
        self.assertEqual(len(quality_point_form.product_ids), 1)
        self.assertEqual(quality_point_form.product_ids[0].id, self.bom.product_id.id)

    def test_delete_move_linked_to_quality_check(self):
        """
        Test that a quality check is deleted when its linked move is deleted.
        """
        self.bom.bom_line_ids.product_id.tracking = 'lot'
        self.bom.bom_line_ids.product_id.is_storable = True
        self.bom.operation_ids[0].quality_point_ids = [Command.create({
            'product_ids': [(4, self.product_1.id)],
            'picking_type_ids': [(4, self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1).id)],
            'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
            'bom_line_id': self.bom.bom_line_ids.filtered(lambda line: line.product_id == self.product_2).id,
        })]
        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom
        mo = mo_form.save()
        mo.action_confirm()
        qc = self.env['quality.check'].search([('product_id', '=', self.bom.product_id.id)])[-1]
        move = qc.move_id
        self.assertEqual(len(qc), 1)
        self.assertFalse(move.move_line_ids)
        move.state = 'draft'
        move.unlink()
        self.assertFalse(move.exists())
        self.assertFalse(qc.exists())

    def test_label_printed_qty(self):
        """
        Check that the label printing instructions print the expected quantities.
        """
        super_product = self.env['product.product'].create({
            'name': 'Super Product',
            'type': 'consu',
            'is_storable': True,
            'tracking': 'lot',
        })
        bom = self.env['mrp.bom'].create({
            'product_id': super_product.id,
            'product_tmpl_id': super_product.product_tmpl_id.id,
            'uom_id': super_product.uom_id.id,
            'product_qty': 1.0,
            'operation_ids': [
                Command.create({'name': 'print label', 'workcenter_id': self.workcenter_1.id})
            ],
            'type': 'normal',
        })

        self.env['quality.point'].create({
            'title': 'Print Label',
            'product_ids': [Command.link(super_product.id)],
            'operation_id': bom.operation_ids.id,
            'test_type_id': self.ref('mrp_workorder.test_type_print_label')
        })
        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = bom
        mo_form.product_qty = 10
        mo = mo_form.save()
        mo.action_confirm()

        quality_check = mo.workorder_ids.current_quality_check_id
        self.assertEqual(quality_check._get_print_qty(), 10)
        with Form(mo) as mo_form:
            mo_form.qty_producing = 7.0
        self.assertEqual(quality_check._get_print_qty(), 7)

    def test_copy_quality_check(self):
        """Test that a copied quality check is correctly added into the chain.

            Scenario:
                - Given a chain of quality checks A -> B -> C.
                - When B is copied.
                - Then the resulting chain should be A -> B -> B' -> C,
                ensuring the copied quality check is inserted directly after its original quality check.
        """
        quality_point = self.env['quality.point'].create({
            'product_ids': [(4, self.product_1.id)],
        })
        quality_alert_team = self.env['quality.alert.team'].create({
            'name': 'Quality Team',
        })
        check_vals = {
            'product_id': self.product_1.id,
            'point_id': quality_point.id,
            'team_id': quality_alert_team.id,
        }
        quality_checks = self.env['quality.check'].create([check_vals, check_vals, check_vals])

        # Create a chain of Quality checks 0 -> 1 -> 2
        quality_checks[1]._insert_in_chain('after', quality_checks[0])
        quality_checks[2]._insert_in_chain('after', quality_checks[1])

        new_check = quality_checks[1].copy()

        # chain of Quality checks should be 0 -> 1 -> Copy of 1 -> 2
        self.assertEqual(quality_checks[1].next_check_id, new_check)
        self.assertEqual(new_check.previous_check_id, quality_checks[1])
        self.assertEqual(new_check.next_check_id, quality_checks[2])

    def test_delete_middle_quality_check_repairs_chain(self):
        """Test that deleting a middle quality check reconnects the surrounding checks.

            Scenario:
                - Given a BOM for P1 with a work order WO1 and 3 quality points linked to WO1.
                - When a MO is confirmed, 3 quality checks A -> B -> C are generated.
                - When B (the middle check) is deleted.
                - Then the chain should be A -> C, ensuring C remains reachable.
        """
        operation = self.bom.operation_ids[0]
        self.env['quality.point'].create([{
            'title': f'QC {i}',
            'product_ids': [Command.link(self.product_1.id)],
            'operation_id': operation.id,
            'test_type_id': self.env.ref('quality.test_type_instructions').id,
        } for i in range(3)])
        mo = self.env['mrp.production'].create({
            'product_id': self.product_1.id,
            'product_qty': 1,
            'bom_id': self.bom.id,
        })
        mo.action_confirm()
        wo = mo.workorder_ids[0]
        self.assertEqual(len(wo.check_ids), 3)

        check_a = wo.check_ids.filtered(lambda c: not c.previous_check_id)
        check_b = check_a.next_check_id
        check_c = check_b.next_check_id

        check_b.unlink()
        self.assertFalse(check_b.exists())
        # Chain should now be A -> C
        self.assertEqual(check_a.next_check_id, check_c)
        self.assertEqual(check_c.previous_check_id, check_a)
        self.assertFalse(check_a.previous_check_id)
        self.assertFalse(check_c.next_check_id)

    def test_merge_mo_from_orderpoints(self):
        """
        Ensure that triggering a manufacturing reordering rule:
        - Updates an existing MO if none of its quality check has been performed yet
        - Creates a new MO if the last MO's product_qty cannot be updated due to a performed quality check
        """
        self.env['mrp.routing.workcenter'].create({
            'name': 'Assembly2',
            'workcenter_id': self.workcenter_1.id,
            'bom_id': self.bom.id,
        })
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        orderpoint = self.env['stock.warehouse.orderpoint'].create({
            'product_id': self.product_1.id,
            'warehouse_id': warehouse.id,
            'product_min_qty': 0,
            'product_max_qty': 0,
            'trigger': 'auto',
        })
        self.env['quality.point'].create({
            'title': 'QC',
            'product_ids': [Command.link(self.product_1.id)],
            'operation_id': self.bom.operation_ids[1].id,
            'test_type_id': self.env.ref('quality.test_type_instructions').id,
        })
        reference = self.env['stock.reference'].create({'name': "lovely reference"})
        deliveries = self.env['stock.picking'].create([{
            'name': f"Lovely Delivery {i}",
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': self.ref('stock.stock_location_customers'),
            'picking_type_id': warehouse.out_type_id.id,
            'move_ids': [Command.create({
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': self.ref('stock.stock_location_customers'),
                'product_id': self.product_1.id,
                'product_uom_qty': 1,
                'reference_ids': [Command.set(reference.ids)],
            })]
        } for i in range(1, 4)])

        deliveries[0].action_confirm()
        mo = self.env['mrp.production'].search([('orderpoint_id', '=', orderpoint.id)], limit=1)
        self.assertRecordValues(mo, [
            {'product_qty': 1.0, 'product_id': self.product_1.id, 'warehouse_id': warehouse.id},
        ])

        deliveries[1].action_confirm()
        self.assertRecordValues(mo, [
            {'product_qty': 2.0, 'product_id': self.product_1.id, 'warehouse_id': warehouse.id},
        ])

        mo.workorder_ids[1].current_quality_check_id.action_next()
        deliveries[2].action_confirm()
        mos = self.env['mrp.production'].search([('orderpoint_id', '=', orderpoint.id)], order='id', limit=2)
        self.assertRecordValues(mos, [
            {'product_qty': 2.0, 'product_id': self.product_1.id, 'warehouse_id': warehouse.id},
            {'product_qty': 1.0, 'product_id': self.product_1.id, 'warehouse_id': warehouse.id},
        ])

    def test_mrp_quality_check_lot_assignment(self):
        """
        Check that only the manufacturing order's lot id is assigned to
        the quality checks, not the components'.
        """
        serial_component, serial_final, lot_component, lot_final, none_component, none_final = \
            self.env['product.product'].create([
                {
                    'name': f'{tracking} tracked {product_type}',
                    'type': 'consu',
                    'is_storable': True,
                    'tracking': tracking,
                }
                for tracking in ('serial', 'lot', False)
                for product_type in ('component', 'final')])
        boms = self.env['mrp.bom'].create([
            {
                'product_id': final.id,
                'product_tmpl_id': final.product_tmpl_id.id,
                'product_qty': 1,
                'type': 'normal',
                'operation_ids': [
                    Command.create({
                        'name': final.name,
                        'workcenter_id': self.workcenter_1.id,
                    })],
                'bom_line_ids': [
                    Command.create({
                        'product_id': component.id,
                        'product_qty': 1,
                    })],
            }
            for final in (serial_final, lot_final, none_final)
            for component in (serial_component, lot_component, none_component)])
        for bom in boms:
            final = bom.product_id
            component = bom.bom_line_ids.product_id
            self.env['quality.point'].create([
                {
                    'title': 'Register Consumed Materials',
                    'operation_id': bom.operation_ids[0].id,
                    'test_type_id': self.env.ref('mrp_workorder.test_type_register_consumed_materials').id,
                    'bom_line_id': bom.bom_line_ids.id,
                },
                {
                    'title': 'Register Production',
                    'operation_id': bom.operation_ids[0].id,
                    'test_type_id': self.env.ref('mrp_workorder.test_type_register_production').id,
                },
            ])
            mo_form = Form(self.env['mrp.production'])
            mo_form.product_id = final
            mo_form.bom_id = bom
            mo = mo_form.save()
            mo.action_confirm()
            if final.tracking:
                mo_form = Form(mo)
                mo_form.lot_producing_ids.set(self.env['stock.lot'].create({
                    'name': f'{final.name} of {mo.name}',
                    'product_id': final.id,
                }))
                mo = mo_form.save()
            if component.tracking:
                mo.move_raw_ids.move_line_ids.lot_id = self.env['stock.lot'].create({
                    'name': f'{component.name} for {mo.name}',
                    'product_id': component.id,
                })
            mo.workorder_ids.check_ids.quality_state = 'pass'
            mo.button_mark_done()
            for qc in mo.workorder_ids.check_ids:
                self.assertEqual(qc.lot_ids, mo.lot_producing_ids,
                                 "The quality check must have the final product's lot id.")

    def test_manufacturing_specific_control_point_test_types(self):
        """
        Test that manufacturing-specific control test types are only available on operations.
        """
        # Include archived records to avoid requiring the option to be enabled
        TestType = self.env['quality.point.test_type'].with_context(active_test=False)
        all_types = TestType.search([])
        manuf_types = TestType.browse([
            self.ref('mrp_workorder.test_type_register_consumed_materials'),
            self.ref('mrp_workorder.test_type_register_production'),
            self.ref('mrp_workorder.test_type_register_byproducts'),
            self.ref('mrp_workorder.test_type_print_label'),
            self.ref('mrp_workorder.test_type_print_lot_label'),
        ])
        restricted_types = all_types - manuf_types
        domain_to_eval = self.env['quality.point']._fields['test_type_id'].domain
        for is_workorder_step, operation_id in product([False, True], repeat=2):
            domain = expr_eval(domain_to_eval.replace("is_workorder_step", str(is_workorder_step)).replace("operation_id", str(operation_id)))
            self.assertEqual(TestType.search(domain), all_types if is_workorder_step and operation_id else restricted_types)
        # Fictional search equivalent to the [('allow_registration', '=', True)]
        self.assertEqual(TestType.search([('allow_registration', 'not in', [False])]), all_types)
