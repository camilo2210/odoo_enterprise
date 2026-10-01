from datetime import datetime

from odoo.tests import tagged, new_test_user, freeze_time, Form
from odoo.addons.planning.tests.common import TestCommonPlanning
from odoo.exceptions import AccessError


@freeze_time("2024-01-01")
@tagged('post_install', '-at_install')
class TestPlanningEquipment(TestCommonPlanning):
    """Tests for the 'Equipment' feature (serial numbers on planning shifts).

    Covers the points raised in review:
      - the equipment notebook is prefilled from the shift customer AND its whole children tree (children, grandchildren, ...);
      - serials linked to several partners are handled;
      - planning users / role>member internal users can READ equipment without 'Inventory / User' rights;
      - planning admins can ADD/REMOVE serials without 'Inventory / User';
      - the notebook is hidden for non-admins when there is nothing to show;
    """

    @classmethod
    def _deliver_lot_to_partner(cls, product, lot_name, partner):
        """Create + validate an outgoing transfer of one tracked unit, returning the lot."""
        customer_loc = cls.env.ref('stock.stock_location_customers')
        stock_loc = cls.env.ref('stock.stock_location_stock')

        # 1) make sure there is stock for that lot
        lot = cls.env['stock.lot'].create({
            'name': lot_name,
            'product_id': product.id,
            'company_id': cls.env.company.id,
        })
        cls.env['stock.quant']._update_available_quantity(
            product, stock_loc, 1.0, lot_id=lot)

        # 2) outgoing picking to the partner
        picking = cls.env['stock.picking'].create({
            'partner_id': partner.id,
            'picking_type_id': cls.env.ref('stock.picking_type_out').id,
            'location_id': stock_loc.id,
            'location_dest_id': customer_loc.id,
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'location_id': stock_loc.id,
                'location_dest_id': customer_loc.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        # assign the lot on the move line
        move = picking.move_ids
        move.move_line_ids.write({'lot_id': lot.id, 'quantity': 1.0})
        move.picked = True
        picking.button_validate()
        return lot

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Enable the equipment feature for testing.
        cls.env['res.config.settings'].create({'group_field_service_allow_equipment': True}).execute()

        Partner = cls.env['res.partner']

        # Customer tree:  A -> B -> C  (C is a grandchild of A).
        # 'other' is unrelated, 'no_lots' has no equipment.
        cls.partner_a = Partner.create({'name': 'Customer A'})
        cls.partner_b = Partner.create({'name': 'Customer B', 'parent_id': cls.partner_a.id})
        cls.partner_c = Partner.create({'name': 'Customer C', 'parent_id': cls.partner_b.id})
        cls.partner_other = Partner.create({'name': 'Customer Other'})
        cls.partner_no_lots = Partner.create({'name': 'Customer Without Equipment'})

        product = cls.env['product.product'].create({
            'name': 'Tracked Product',
            'is_storable': True,
            'tracking': 'lot',
        })

        cls.lot_a = cls._deliver_lot_to_partner(product, 'SN-A', cls.partner_a)
        cls.lot_b = cls._deliver_lot_to_partner(product, 'SN-B', cls.partner_b)
        cls.lot_c = cls._deliver_lot_to_partner(product, 'SN-C', cls.partner_c)
        cls.lot_other = cls._deliver_lot_to_partner(product, 'SN-OTHER', cls.partner_other)

        # Users created WITHOUT any Inventory access on purpose.
        cls.planning_user = new_test_user(cls.env, login='eq_planning_user', groups='planning.group_planning_user')
        cls.planning_admin = new_test_user(cls.env, login='eq_planning_admin', groups='planning.group_planning_manager')
        cls.internal_user = new_test_user(cls.env, login='eq_internal_user', groups='base.group_user')

    def _create_slot(self, partner=None):
        return self.env['planning.slot'].create({
            'start_datetime': datetime(2024, 1, 1, 8, 0, 0),
            'end_datetime': datetime(2024, 1, 1, 17, 0, 0),
            'partner_id': partner.id if partner else False,
            'resource_ids': (self.planning_admin.resource_ids + self.planning_user.resource_ids + self.internal_user.resource_ids).ids,
            'state': '2_published',
        })

    # ------------------------------------------------------------------
    # _compute_lot_ids : prefilling from the shift customer
    # ------------------------------------------------------------------
    def test_lot_ids_from_customer(self):
        slot = self._create_slot(self.partner_a)
        self.assertIn(self.lot_a, slot.lot_ids, "Equipment from the shift customer should be included.")

    def test_lot_ids_includes_whole_subtree(self):
        """Selecting an ancestor pulls equipment of children AND grandchildren."""
        slot = self._create_slot(self.partner_a)
        self.assertIn(self.lot_a, slot.lot_ids, "Equipment from the shift customer should be included.")
        self.assertIn(self.lot_b, slot.lot_ids, "Equipment from the shift customer children should be included.")
        self.assertIn(self.lot_c, slot.lot_ids, "Equipment from the shift customer grandchildren should be included.")

    def test_lot_ids_excludes_ancestors(self):
        """Selecting a child pulls its own subtree, not the parent's equipment."""
        slot = self._create_slot(self.partner_b)
        self.assertIn(self.lot_b, slot.lot_ids, "Equipment from the shift customer should be included.")
        self.assertIn(self.lot_c, slot.lot_ids, "Equipment from the shift customer children should be included.")
        self.assertNotIn(self.lot_a, slot.lot_ids, "Equipment from the parent customer shouldn't be included.")

    def test_lot_ids_excludes_unrelated(self):
        slot = self._create_slot(self.partner_a)
        self.assertNotIn(self.lot_other, slot.lot_ids, "Equipment from the other customer shouldn't be included.")

    def test_lot_ids_empty_without_customer(self):
        slot = self._create_slot()
        self.assertFalse(slot.lot_ids, "Without a shift customer, the equipment list should be empty.")

    def test_lot_ids_recomputed_on_customer_change(self):
        slot = self._create_slot(self.partner_other)
        self.assertIn(self.lot_other, slot.lot_ids, "Equipment from the shift customer should be included.")
        slot.partner_id = self.partner_a
        self.assertIn(self.lot_a, slot.lot_ids, "Equipment from the new shift customer should be included.")
        self.assertNotIn(self.lot_other, slot.lot_ids, "Equipment from the old customer should be removed.")

    # ------------------------------------------------------------------
    # delivery_date immediate load
    # ------------------------------------------------------------------
    def test_delivery_date_shown_before_the_shift_is_saved(self):
        """Picking the customer lists its equipment, delivery date included.

        The shift is not saved at that point: the onchange links the lots to it, and
        the form keeps their ids, which is what the equipment page is built from.
        """
        # A cached value would hide a compute that cannot reach the transfers.
        self.env.invalidate_all()
        slot = self._create_slot(self.partner_no_lots)
        form = Form(slot.with_user(self.planning_admin))

        form.partner_id = self.partner_a

        lots = self.env['stock.lot'].browse(form.lot_ids.ids)

        self.assertEqual(lots, self.lot_a + self.lot_b + self.lot_c,
                         "The customer's equipment should be listed before the shift is saved.")
        self.assertTrue(all(lots.mapped('delivery_date')),
                        "Each piece of equipment should carry the date it was delivered on.")
        self.assertTrue(all(lots.mapped('is_delivery_date_visible')),
                        "The delivery date should be shown for each of them.")
        self.assertEqual(lots.mapped('delivery_date'), [self.lot_a.delivery_date, self.lot_b.delivery_date, self.lot_c.delivery_date],
                         "The delivery dates should be the ones from the transfers")

    # ------------------------------------------------------------------
    # Access rights : no 'Inventory / User' required
    # ------------------------------------------------------------------
    def test_planning_user_reads_equipment_without_inventory(self):
        self.assertFalse(self.planning_user.has_group('stock.group_stock_user'), "Planning users should not have 'Inventory / User' rights.")
        slot = self._create_slot(self.partner_a).with_user(self.planning_user)
        self.assertTrue(slot.lot_ids.mapped('name'), "Planning users must be able to read equipment without 'Inventory / User' rights.")

    def test_internal_user_reads_serials_without_inventory(self):
        self.assertFalse(self.internal_user.has_group('stock.group_stock_user'), "role>member users must read serials without 'Inventory / User' rights.")
        # Read the serial directly as a plain internal user -> relies on the
        # stock.lot ACL granted to base.group_user. Must not raise.
        with self.assertRaises(AccessError, msg="Internal user without any access to planning cannot read serials without Inventory access"):
            self.lot_a.with_user(self.internal_user).read(['name', 'product_id', 'ref'])

    def test_planning_admin_edits_equipment_without_inventory(self):
        self.assertFalse(self.planning_admin.has_group('stock.group_stock_user'), "Planning admins should not have 'Inventory / User' rights.")
        slot = self._create_slot(self.partner_a).with_user(self.planning_admin)
        slot.write({'lot_ids': [(3, self.lot_a.id)]})   # remove
        self.assertNotIn(self.lot_a, slot.lot_ids, "Planning admins must be able to remove equipment without 'Inventory / User' rights.")
        slot.write({'lot_ids': [(4, self.lot_a.id)]})   # add back
        self.assertIn(self.lot_a, slot.lot_ids, "Planning admins must be able to add equipment without 'Inventory / User' rights.")

    # ------------------------------------------------------------------
    # equipment notebook visibility (visible if `can_edit and partner_id and lot_ids`)
    # ------------------------------------------------------------------
    def test_page_hidden_without_customer(self):
        slot = self._create_slot()
        form = Form(slot.with_user(self.planning_user))
        self.assertTrue(form._get_modifier('lot_ids', 'invisible'),
                        "Without a shift customer, the equipment page should be hidden.")

    def test_delivery_date_column_dropped_without_the_equipment_feature(self):
        """The list column must disappear with the feature, not just show empty cells.

        A list only blanks the cells of an `invisible` field, the column itself stays.
        """
        lot_list = self.env.ref('planning_field_service_stock.view_production_lot_view_tree')

        arch = self.env['stock.lot'].with_user(self.planning_admin).get_view(lot_list.id, 'list')['arch']
        self.assertIn('delivery_date', arch, "With the equipment feature on, the column should be part of the list.")

        self.env['res.config.settings'].create({'group_field_service_allow_equipment': False}).execute()

        arch = self.env['stock.lot'].with_user(self.planning_admin).get_view(lot_list.id, 'list')['arch']
        self.assertNotIn('delivery_date', arch, "With the equipment feature off, the column should be gone from the list.")

    def test_lot_ids_manual_deletion_preserved(self):
        """Test that manually removing equipment is preserved when recomputing"""

        slot = self._create_slot(self.partner_a)
        self.assertEqual(slot.lot_ids, self.lot_a | self.lot_b | self.lot_c,
                         "Should initially have lot A, B, and C")

        with Form(slot.with_user(self.planning_admin)) as slot_form:
            slot_form.lot_ids.remove(self.lot_b.id)
            slot_form.end_datetime = datetime(2024, 1, 1, 18, 0, 0)

        self.assertEqual(slot.lot_ids, self.lot_a | self.lot_c,
                         "Manual deletions should be preserved when editing other fields.")

        with Form(slot.with_user(self.planning_admin)) as slot_form:
            slot_form.partner_id = self.partner_other

        self.assertEqual(slot.lot_ids, self.lot_other,
                         "Changing the customer entirely should reset the equipment list.")
