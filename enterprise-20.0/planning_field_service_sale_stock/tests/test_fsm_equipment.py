from odoo import Command
from odoo.addons.planning_field_service_sale_timesheet.tests.common import TestPlanningFieldServiceSaleTimesheetCommon


class TestFsmEquipmentFromMaterials(TestPlanningFieldServiceSaleTimesheetCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)

        cls.product_lot, cls.product_serial = cls.env['product.product'].create([{
            'name': 'Tracked by lot',
            'list_price': 60,
            'is_storable': True,
            'invoice_policy': 'delivery',
            'taxes_id': False,
            'tracking': 'lot',
        }, {
            'name': 'Tracked by serial',
            'list_price': 90,
            'is_storable': True,
            'invoice_policy': 'delivery',
            'taxes_id': False,
            'tracking': 'serial',
        }])
        cls.lot_1, cls.serial_1, cls.serial_2 = cls.env['stock.lot'].create([{
            'name': 'lot_1',
            'product_id': cls.product_lot.id,
        }, {
            'name': 'serial_1',
            'product_id': cls.product_serial.id,
        }, {
            'name': 'serial_2',
            'product_id': cls.product_serial.id,
        }])
        cls.env['stock.quant'].with_context(inventory_mode=True).create([{
            'product_id': cls.product_lot.id,
            'inventory_quantity': 10,
            'lot_id': cls.lot_1.id,
            'location_id': cls.warehouse.lot_stock_id.id,
        }, {
            'product_id': cls.product_serial.id,
            'inventory_quantity': 1,
            'lot_id': cls.serial_1.id,
            'location_id': cls.warehouse.lot_stock_id.id,
        }, {
            'product_id': cls.product_serial.id,
            'inventory_quantity': 1,
            'lot_id': cls.serial_2.id,
            'location_id': cls.warehouse.lot_stock_id.id,
        }]).action_apply_inventory()

        cls.env['res.config.settings'].create({'group_field_service_allow_equipment': True}).execute()
        cls.customer_lot = cls._deliver_lot_to_partner(cls.product_lot, 'lot_owned', cls.partner_1)

        # the equipment of the customer is prefilled on the intervention when its customer is set
        cls.intervention.write({
            'resource_ids': cls.henri_employee.resource_id.ids,
            'state': '3_in_progress',
            'partner_id': cls.partner_1.id,
        })
        cls.intervention._ensure_sale_order_set()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @classmethod
    def _deliver_lot_to_partner(cls, product, lot_name, partner):
        """Create + validate an outgoing transfer of one tracked unit, returning the lot."""
        stock_loc = cls.warehouse.lot_stock_id
        customer_loc = cls.env.ref('stock.stock_location_customers')
        lot = cls.env['stock.lot'].create({
            'name': lot_name,
            'product_id': product.id,
            'company_id': cls.env.company.id,
        })
        cls.env['stock.quant']._update_available_quantity(product, stock_loc, 1.0, lot_id=lot)
        picking = cls.env['stock.picking'].create({
            'partner_id': partner.id,
            'picking_type_id': cls.warehouse.out_type_id.id,
            'location_id': stock_loc.id,
            'location_dest_id': customer_loc.id,
            'move_ids': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'location_id': stock_loc.id,
                'location_dest_id': customer_loc.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.move_line_ids.write({'lot_id': lot.id, 'quantity': 1.0})
        picking.move_ids.picked = True
        picking.button_validate()
        return lot

    def _add_lot_product(self, product, lines):
        wizard_action = product.with_context(intervention_id=self.intervention.id).action_assign_serial()
        wizard = self.env['field.service.stock.tracking'].browse(wizard_action['res_id'])
        wizard.write({
            'tracking_line_ids': [Command.create({
                'product_id': product.id,
                'quantity': line['qty'],
                'lot_id': line['lot_id'],
            }) for line in lines],
        })
        wizard.generate_lot()
        return wizard

    def _add_serial_product(self, product, lots):
        wizard_action = product.with_context(intervention_id=self.intervention.id).action_assign_serial()
        wizard = self.env['field.service.stock.tracking'].browse(wizard_action['res_id'])
        wizard.write({
            'tracking_line_ids': [Command.create({'lot_id': lot.id}) for lot in lots],
        })
        wizard.generate_lot()
        return wizard

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_added_lot_product_is_in_equipment(self):
        """A material tracked by lot added to the intervention shows up in its equipment."""
        self.assertNotIn(self.lot_1, self.intervention.lot_ids, "The lot is not customer equipment yet.")

        self._add_lot_product(self.product_lot, [{'lot_id': self.lot_1.id, 'qty': 3}])

        self.assertEqual(self.intervention.material_line_product_count, 3, "The material should be linked to the intervention.")
        self.assertIn(self.lot_1, self.intervention.lot_ids, "The lot of the added material should be on the equipment page.")

    def test_added_serial_products_are_in_equipment(self):
        """Materials tracked by serial number added to the intervention show up in its equipment."""
        self._add_serial_product(self.product_serial, [self.serial_1, self.serial_2])

        self.assertEqual(self.intervention.material_line_product_count, 2, "Both materials should be linked to the intervention.")
        self.assertIn(self.serial_1, self.intervention.lot_ids, "The first added serial number should be on the equipment page.")
        self.assertIn(self.serial_2, self.intervention.lot_ids, "The second added serial number should be on the equipment page.")

    def test_added_lots_do_not_erase_customer_equipment(self):
        """The materials added to the intervention come on top of the customer equipment."""
        self.assertEqual(self.intervention.lot_ids, self.customer_lot, "The intervention starts with the equipment of its customer.")

        self._add_lot_product(self.product_lot, [{'lot_id': self.lot_1.id, 'qty': 1}])

        self.assertEqual(
            self.intervention.lot_ids,
            self.customer_lot | self.lot_1,
            "The added material should be added to the customer equipment, not replace it.",
        )

    def test_added_lots_removed_from_equipment_with_the_material(self):
        """Removing the material from the intervention removes its lot from the equipment."""
        wizard = self._add_lot_product(self.product_lot, [{'lot_id': self.lot_1.id, 'qty': 4}])
        self.assertIn(self.lot_1, self.intervention.lot_ids, "The lot of the added material should be on the equipment page.")

        wizard.write({'tracking_line_ids': [Command.clear()]})
        wizard.generate_lot()

        self.assertFalse(self.intervention.material_line_product_count, "The material should no longer be linked to the intervention.")
        self.assertNotIn(self.lot_1, self.intervention.lot_ids, "The lot should be gone from the equipment page along with the material.")

    def test_added_lots_in_equipment_of_the_right_intervention(self):
        """The lot lands on the intervention the material was added to, not on its siblings."""
        self.second_intervention.write({
            'resource_ids': self.marcel_employee.resource_id.ids,
            'state': '3_in_progress',
            'partner_id': self.partner_1.id,
        })
        self.second_intervention._ensure_sale_order_set()

        self._add_lot_product(self.product_lot, [{'lot_id': self.lot_1.id, 'qty': 1}])

        self.assertIn(self.lot_1, self.intervention.lot_ids, "The lot should be on the equipment page of the intervention it was added to.")
        self.assertNotIn(self.lot_1, self.second_intervention.lot_ids, "The lot should not leak to another intervention of the same customer.")
