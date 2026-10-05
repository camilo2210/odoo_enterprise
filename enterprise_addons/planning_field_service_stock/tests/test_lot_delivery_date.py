from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, freeze_time, tagged


@tagged('post_install', '-at_install')
class TestLotDeliveryDate(TransactionCase):
    """Tests for stock.lot.delivery_date / is_delivery_date_visible.

    'delivery_date' must report when the customer received the unit:
      - multi-step routes (pick + ship): the ship step, not the pick step;
      - inter-warehouse resupply: ignored
      - re-delivered units: the latest delivery, not the first one;
      - returned units: no delivery date at all.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.config.settings'].create({'group_field_service_allow_equipment': True}).execute()

        cls.warehouse = cls.env.ref('stock.warehouse0')
        # 2-step delivery: creates the 'Pick' operation type (code `internal`) and the WH/Output location.
        cls.warehouse.delivery_steps = 'pick_ship'

        cls.stock_loc = cls.warehouse.lot_stock_id
        cls.output_loc = cls.warehouse.wh_output_stock_loc_id
        cls.customer_loc = cls.env.ref('stock.stock_location_customers')

        # Transit location used by inter-warehouse resupply routes; inactive by default.
        cls.transit_loc = cls.env.company.internal_transit_location_id
        cls.transit_loc.active = True

        cls.customer = cls.env['res.partner'].create({'name': 'Equipment Customer'})
        cls.other_customer = cls.env['res.partner'].create({'name': 'Other Equipment Customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'Tracked Equipment',
            'is_storable': True,
            'tracking': 'lot',
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _new_lot(self, name, quantity=1.0, location=None):
        """Create a lot and put `quantity` unit(s) of it in `location`."""
        lot = self.env['stock.lot'].create({
            'name': name,
            'product_id': self.product.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.quant']._update_available_quantity(
            self.product, location or self.stock_loc, quantity, lot_id=lot)
        return lot

    def _create_transfer(self, lot, picking_type, src, dest, partner=None, quantity=1.0):
        """Create a confirmed transfer of `quantity` unit(s) of `lot`, ready to be validated."""
        picking = self.env['stock.picking'].create({
            'partner_id': partner.id if partner else False,
            'picking_type_id': picking_type.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': quantity,
                'location_id': src.id,
                'location_dest_id': dest.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        move = picking.move_ids
        if move.move_line_ids:
            move.move_line_ids[0].write({'lot_id': lot.id, 'quantity': quantity})
            (move.move_line_ids - move.move_line_ids[0]).unlink()
        else:
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': self.product.id,
                'lot_id': lot.id,
                'quantity': quantity,
                'location_id': src.id,
                'location_dest_id': dest.id,
            })
        move.picked = True
        return picking

    def _validate(self, picking, done_at):
        """Validate `picking`, so that its `date_done` is exactly `done_at`."""
        with freeze_time(done_at):
            picking.button_validate()
        self.assertEqual(picking.state, 'done', "The transfer should have been validated.")
        self.assertEqual(picking.date_done, done_at, "The transfer should be done at the frozen time.")
        return picking

    def _transfer(self, lot, picking_type, src, dest, done_at, partner=None, quantity=1.0):
        return self._validate(self._create_transfer(lot, picking_type, src, dest, partner, quantity), done_at)

    def _reload(self, lot):
        """`delivery_date`, `delivery_ids` and `partner_ids` are non-stored computes
        that nothing invalidates, so drop the cache before asserting on them."""
        lot.invalidate_recordset()
        return lot

    # ------------------------------------------------------------------
    # delivery_date
    # ------------------------------------------------------------------
    def test_delivery_date_single_step(self):
        """One-step delivery: the delivery date is the transfer's validation date."""
        lot = self._new_lot('SN-SINGLE')
        done_at = datetime(2024, 1, 8, 15, 0, 0)
        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc,
                       done_at, partner=self.customer)

        self.assertEqual(self._reload(lot).delivery_date, done_at,
                         "The delivery date should be the validation date of the delivery.")

    def test_delivery_date_multi_step_uses_ship_step(self):
        """2-step delivery: the Pick date is ignored, only the Delivery Order counts.

        When the Pick is validated the unit is still in the warehouse, so its date
        must not be reported as the customer's delivery date.
        """
        lot = self._new_lot('SN-MULTISTEP')
        picked_at = datetime(2024, 1, 5, 10, 0, 0)
        shipped_at = datetime(2024, 1, 8, 15, 0, 0)

        pick = self._transfer(lot, self.warehouse.pick_type_id, self.stock_loc, self.output_loc, picked_at)
        ship = self._transfer(lot, self.warehouse.out_type_id, self.output_loc, self.customer_loc, shipped_at, partner=self.customer)

        self.assertEqual(self.warehouse.pick_type_id.code, 'internal', "The Pick step of a multi-step route is an internal operation type.")
        lot = self._reload(lot)
        self.assertNotIn(pick, lot.delivery_ids, "The Pick step is not a delivery.")
        self.assertIn(ship, lot.delivery_ids, "The Delivery Order is the actual delivery.")
        self.assertEqual(lot.delivery_date, shipped_at, "The delivery date should be the ship date, not the pick date.")

    def test_delivery_date_ignores_inter_warehouse_resupply(self):
        """A resupply leg towards a transit location is not a customer delivery.

        Resupplying a warehouse from another one reuses the supplying warehouse's
        `outgoing` operation type, so such a transfer ends up in `delivery_ids`
        even though it lands in a transit location instead of a customer one.
        """
        lot = self._new_lot('SN-RESUPPLY')
        resupplied_at = datetime(2024, 1, 2, 9, 0, 0)
        moved_to_stock_at = datetime(2024, 1, 3, 9, 0, 0)
        delivered_at = datetime(2024, 1, 10, 16, 0, 0)

        # WH/Stock -> Transit, with the `outgoing` operation type (as the resupply rule does).
        resupply = self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.transit_loc, resupplied_at)
        # Transit -> WH/Stock, then the real delivery to the customer.
        self._transfer(lot, self.warehouse.in_type_id, self.transit_loc, self.stock_loc, moved_to_stock_at)
        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, delivered_at, partner=self.customer)

        lot = self._reload(lot)
        self.assertIn(resupply, lot.delivery_ids, "`delivery_ids` includes the resupply leg, since it uses an outgoing operation type.")
        self.assertEqual(lot.delivery_date, delivered_at, "The resupply leg should be ignored: only the transfer to the customer counts.")

    def test_delivery_date_latest_delivery_wins(self):
        """A unit returned then delivered again reports its latest delivery."""
        lot = self._new_lot('SN-REDELIVERED')
        first_delivery_at = datetime(2024, 1, 5, 11, 0, 0)
        returned_at = datetime(2024, 1, 10, 9, 0, 0)
        second_delivery_at = datetime(2024, 1, 20, 14, 0, 0)

        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, first_delivery_at, partner=self.customer)
        self.assertEqual(self._reload(lot).delivery_date, first_delivery_at, "The delivery date should be the first delivery so far.")

        # The customer returns the unit, then it is delivered again.
        self._transfer(lot, self.warehouse.in_type_id, self.customer_loc, self.stock_loc, returned_at, partner=self.customer)
        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, second_delivery_at, partner=self.customer)

        self.assertEqual(self._reload(lot).delivery_date, second_delivery_at, "After a re-delivery, the delivery date should be the latest delivery.")

    def test_delivery_date_cleared_by_a_return(self):
        """A unit sent back by the customer has no delivery date anymore."""
        lot = self._new_lot('SN-RETURNED')
        delivered_at = datetime(2024, 1, 5, 11, 0, 0)
        returned_at = datetime(2024, 1, 10, 9, 0, 0)

        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, delivered_at, partner=self.customer)
        self.assertEqual(self._reload(lot).delivery_date, delivered_at, "The delivery date should be set while the unit is at the customer.")

        return_picking = self._transfer(lot, self.warehouse.in_type_id, self.customer_loc, self.stock_loc, returned_at, partner=self.customer)

        lot = self._reload(lot)
        self.assertNotIn(return_picking, lot.delivery_ids, "A return is an incoming transfer, it is not part of `delivery_ids`.")
        self.assertFalse(lot.delivery_date, "A returned unit is back in the warehouse: it should have no delivery date.")

    def test_delivery_date_kept_after_a_partial_return(self):
        """Returning part of the lot leaves the rest at the customer."""
        lot = self._new_lot('SN-PARTIAL', quantity=3.0)
        delivered_at = datetime(2024, 1, 5, 11, 0, 0)
        returned_at = datetime(2024, 1, 10, 9, 0, 0)

        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, delivered_at, partner=self.customer, quantity=3.0)
        self._transfer(lot, self.warehouse.in_type_id, self.customer_loc, self.stock_loc, returned_at, partner=self.customer, quantity=1.0)

        self.assertEqual(self._reload(lot).delivery_date, delivered_at,
                         "2 of the 3 units are still at the customer: the delivery date should be kept.")

    def test_delivery_date_cleared_once_everything_came_back(self):
        """The delivery date goes away on the return that completes the delivered quantity."""
        lot = self._new_lot('SN-PARTIAL-THEN-FULL', quantity=3.0)
        delivered_at = datetime(2024, 1, 5, 11, 0, 0)

        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, delivered_at, partner=self.customer, quantity=3.0)
        self._transfer(lot, self.warehouse.in_type_id, self.customer_loc, self.stock_loc, datetime(2024, 1, 10, 9, 0, 0), partner=self.customer, quantity=1.0)
        self.assertEqual(self._reload(lot).delivery_date, delivered_at, "One unit back out of three: still delivered.")

        self._transfer(lot, self.warehouse.in_type_id, self.customer_loc, self.stock_loc, datetime(2024, 1, 12, 9, 0, 0), partner=self.customer, quantity=2.0)

        self.assertFalse(self._reload(lot).delivery_date,
                         "The 3 delivered units came back: the lot should have no delivery date.")

    def test_delivery_date_without_delivery(self):
        lot = self._new_lot('SN-IN-STOCK')
        self.assertFalse(self._reload(lot).delivery_date, "A unit still in stock should have no delivery date.")

    def test_delivery_date_pending_delivery(self):
        """A delivery that is not validated yet doesn't set a delivery date."""
        lot = self._new_lot('SN-PENDING')
        self._create_transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, partner=self.customer)

        self.assertFalse(self._reload(lot).delivery_date, "An unvalidated delivery should not set a delivery date.")

    # ------------------------------------------------------------------
    # writing delivery_date back on the transfer
    # ------------------------------------------------------------------
    def test_delivery_date_written_back_on_the_delivery(self):
        """Setting the delivery date corrects the transfer it was read from."""
        lot = self._new_lot('SN-CORRECTED')
        done_at = datetime(2024, 1, 8, 15, 0, 0)
        corrected_at = datetime(2024, 1, 3, 9, 30, 0)

        delivery = self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, done_at, partner=self.customer)
        self._reload(lot).delivery_date = corrected_at

        self.assertEqual(delivery.date_done, corrected_at, "The delivery should have been dated back.")
        self.assertEqual(delivery.move_ids.date, corrected_at, "`stock.picking` should have propagated the date to its moves.")
        self.assertEqual(self._reload(lot).delivery_date, corrected_at, "The lot should report the corrected date.")

    def test_delivery_date_written_back_on_the_ship_step(self):
        """2-step delivery: the write goes to the Delivery Order, not to the Pick."""
        lot = self._new_lot('SN-MULTISTEP-WRITE')
        picked_at = datetime(2024, 1, 5, 10, 0, 0)
        shipped_at = datetime(2024, 1, 8, 15, 0, 0)
        corrected_at = datetime(2024, 1, 9, 8, 0, 0)

        pick = self._transfer(lot, self.warehouse.pick_type_id, self.stock_loc, self.output_loc, picked_at)
        ship = self._transfer(lot, self.warehouse.out_type_id, self.output_loc, self.customer_loc, shipped_at, partner=self.customer)

        self._reload(lot).delivery_date = corrected_at

        self.assertEqual(ship.date_done, corrected_at, "The Delivery Order should carry the new date.")
        self.assertEqual(pick.date_done, picked_at, "The Pick step should be left untouched.")

    def test_delivery_date_not_writable_without_delivery(self):
        """Without a delivery there is nothing to write the date on."""
        lot = self._new_lot('SN-NOT-DELIVERED')

        with self.assertRaises(UserError):
            self._reload(lot).delivery_date = datetime(2024, 1, 8, 15, 0, 0)

    def test_delivery_date_cannot_be_emptied(self):
        """Emptying the date would leave the transfer without one: say so."""
        lot = self._new_lot('SN-EMPTIED')
        done_at = datetime(2024, 1, 8, 15, 0, 0)
        delivery = self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, done_at, partner=self.customer)

        with self.assertRaises(UserError):
            self._reload(lot).delivery_date = False

        self.assertEqual(delivery.date_done, done_at, "The delivery should have kept its date.")

    def test_lot_can_be_created_from_a_form(self):
        """Creating a lot must not be blocked by the delivery date write-back.

        A form sends every field it displays, `delivery_date` included, so `create`
        runs its inverse with an empty value on a lot that was never delivered.
        """
        lot_form = Form(self.env['stock.lot'])
        lot_form.name = 'SN-FROM-FORM'
        lot_form.product_id = self.product
        lot = lot_form.save()

        self.assertFalse(lot.delivery_date, "A lot that was just created has no delivery date.")

    def test_lot_cannot_be_created_with_a_delivery_date(self):
        """Only the empty date a form sends is dropped, a real one is still refused."""
        with self.assertRaises(UserError):
            self.env['stock.lot'].create({
                'name': 'SN-CREATED-WITH-DATE',
                'product_id': self.product.id,
                'company_id': self.env.company.id,
                'delivery_date': datetime(2024, 1, 8, 15, 0, 0),
            })

    # ------------------------------------------------------------------
    # is_delivery_date_visible
    # ------------------------------------------------------------------
    def test_is_delivery_date_visible_for_single_customer(self):
        lot = self._new_lot('SN-VISIBLE')
        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, datetime(2024, 1, 8, 15, 0, 0), partner=self.customer)

        self.assertTrue(self._reload(lot).is_delivery_date_visible, "The delivery date should be shown for a unit delivered to a single customer.")

    def test_is_delivery_date_visible_hidden_without_customer(self):
        lot = self._new_lot('SN-NO-CUSTOMER')
        self.assertFalse(self._reload(lot).is_delivery_date_visible, "The delivery date should be hidden for a unit that was never delivered.")

    def test_is_delivery_date_visible_hidden_for_several_customers(self):
        """Two units of the same lot at two customers: no single delivery to show."""
        lot = self._new_lot('SN-SHARED', quantity=2.0)
        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, datetime(2024, 1, 8, 15, 0, 0), partner=self.customer)
        self._transfer(lot, self.warehouse.out_type_id, self.stock_loc, self.customer_loc, datetime(2024, 1, 9, 15, 0, 0), partner=self.other_customer)

        lot = self._reload(lot)
        self.assertEqual(len(lot.partner_ids), 2, "The lot should be linked to both customers.")
        self.assertFalse(lot.is_delivery_date_visible, "The delivery date should be hidden when the lot is spread over several customers.")
