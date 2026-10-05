from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import new_test_user

from .common import MaintenanceContractCommon


class TestContractEquipment(MaintenanceContractCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesperson = new_test_user(
            cls.env, login='contract_salesperson',
            groups='sales_team.group_sale_salesman_all_leads',
        )

    def test_a_renewal_keeps_covering_the_same_equipment(self):
        self.contract.next_invoice_date = fields.Date.today() + relativedelta(months=1)
        self.contract.prepare_renewal_order()
        renewal = self.contract.subscription_child_ids
        renewed_line = renewal.order_line.filtered(lambda line: line.product_id == self.maintenance)
        self.assertEqual(renewed_line.lot_ids, self.lot_1 + self.lot_2,
                         "A renewed contract keeps covering the machines of the one it renews.")

    def test_an_upsell_covers_the_same_equipment(self):
        self.contract.next_invoice_date = fields.Date.today() + relativedelta(months=1)
        self.contract.prepare_upsell_order()
        upsell = self.contract.subscription_child_ids
        upsold_line = upsell.order_line.filtered(lambda line: line.product_id == self.maintenance)
        self.assertFalse(upsell.is_subscription, "An upsell is not a contract of its own.")
        self.assertEqual(upsold_line.lot_ids, self.lot_1 + self.lot_2,
                         "An upsell is about the equipment the customer already has.")

    def _order_one_more_machine(self):
        machine_line = self.contract.order_line.filtered(lambda line: line.product_id == self.machine)
        machine_line.product_uom_qty += 1
        self.contract_line.invalidate_recordset()

    def test_removed_equipment_does_not_come_back_when_the_demand_changes(self):
        self.contract_line.lot_ids = self.lot_2

        self._order_one_more_machine()

        self.assertEqual(self.contract_line.lot_ids, self.lot_2,
                         "Ordering one more machine should not put the removed serial back on the contract.")

    def test_a_later_delivery_only_adds_what_it_delivers(self):
        self.contract_line.lot_ids = self.lot_2
        self._order_one_more_machine()

        self._put_in_stock(['SN-EXTRA'])
        self._deliver(self.contract, ['SN-EXTRA'])

        self.contract_line.invalidate_recordset()
        self.assertEqual(self.contract_line.lot_ids.mapped('name'), ['SN-2', 'SN-EXTRA'],
                         "A delivery adds the machines it hands over, and leaves the rest alone.")

    def test_allow_lot_update_only_on_recurring_services(self):
        order = self._sell_machines_under_contract(
            self.customer, ['SN-CONSULT'],
            extra_lines=[{'product_id': self.consultancy.id, 'product_uom_qty': 1}],
        )
        allow_lot_update = {line.product_id: line.allow_lot_update for line in order.order_line}
        self.assertTrue(allow_lot_update[self.maintenance],
                        "A recurring service is a contract, it can cover equipment.")
        self.assertFalse(allow_lot_update[self.consultancy],
                         "A one shot service is not a contract, it covers no equipment.")
        self.assertFalse(allow_lot_update[self.machine],
                         "A storable product is the equipment, it doesn't cover any.")

    def test_a_transfer_dropping_an_empty_line_still_validates(self):
        """ Stock unlinks the move lines left at zero, they are gone by the time we look. """
        order = self._sell_machines_under_contract(self.customer, ['SN-EMPTY'], deliver=False)
        picking = order.picking_ids
        picking.action_assign()
        move = picking.move_ids.filtered(lambda m: m.product_id == self.machine)
        move.move_line_ids.unlink()
        self.env['stock.move.line'].create([{
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': self.machine.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
            'quantity': quantity,
            'lot_id': self.env['stock.lot'].search([('name', '=', 'SN-EMPTY')]).id if quantity else False,
        } for quantity in (1, 0)])
        move.picked = True

        picking.button_validate()

        contract_line = order.order_line.filtered(lambda line: line.product_id == self.maintenance)
        self.assertEqual(contract_line.lot_ids.mapped('name'), ['SN-EMPTY'],
                         "The delivered machine still lands on the contract.")

    def test_delivered_serials_land_on_the_contract_line(self):
        self.assertEqual(self.contract_line.lot_ids, self.lot_1 + self.lot_2,
                         "Every serial number delivered by the order should end up on its contract line.")

    def test_no_equipment_before_the_delivery_is_validated(self):
        order = self._sell_machines_under_contract(self.customer, ['SN-LATE'], deliver=False)
        contract_line = order.order_line.filtered(lambda line: line.product_id == self.maintenance)
        self.assertFalse(contract_line.lot_ids,
                         "As long as nothing is delivered, the contract covers no equipment.")

        self._deliver(order, ['SN-LATE'])
        self.assertEqual(contract_line.lot_ids.mapped('name'), ['SN-LATE'],
                         "Validating the transfer should put the delivered serial on the contract line.")

    def test_one_shot_service_line_covers_nothing(self):
        order = self._sell_machines_under_contract(
            self.customer, ['SN-ONESHOT'],
            extra_lines=[{'product_id': self.consultancy.id, 'product_uom_qty': 1}],
        )
        consultancy_line = order.order_line.filtered(lambda line: line.product_id == self.consultancy)
        self.assertFalse(consultancy_line.lot_ids,
                         "A line that is not a contract should never be given the delivered equipment.")

    def test_a_duplicated_order_starts_without_equipment(self):
        copied_line = self.contract.copy().order_line.filtered(lambda line: line.product_id == self.maintenance)
        self.assertFalse(copied_line.lot_ids, "A duplicate has delivered nothing yet, so it cannot claim any equipment.")

    def test_equipment_is_reserved_to_inventory_users(self):
        with self.assertRaises(AccessError, msg="The equipment of a contract line is Inventory data."):
            self.contract_line.with_user(self.salesperson).read(['lot_ids'])

    def test_deliveries_add_up_and_never_undo_a_removal(self):
        """ The whole life of the equipment list, in the order a salesperson lives it. """
        self.assertEqual(self.contract_line.lot_ids, self.lot_1 + self.lot_2,
                         "The contract starts with what the order delivered.")

        self._deliver_one_more('SN-3')
        self.assertEqual(self.contract_line.lot_ids.mapped('name'), ['SN-1', 'SN-2', 'SN-3'],
                         "A new delivery adds its machine to the contract.")

        self.contract_line.lot_ids -= self.lot_1
        self._deliver_one_more('SN-4')
        self.assertEqual(self.contract_line.lot_ids.mapped('name'), ['SN-2', 'SN-3', 'SN-4'],
                         "A later delivery adds its own machine without bringing back a removed one.")

        self.maintenance.modified(['recurring_invoice'])
        self.assertEqual(self.contract_line.lot_ids.mapped('name'), ['SN-2', 'SN-3', 'SN-4'],
                         "Running the compute again must not rebuild the list with the four serials the order delivered.")

    def _deliver_one_more(self, serial):
        self._put_in_stock([serial])
        machine_line = self.contract.order_line.filtered(lambda line: line.product_id == self.machine)
        machine_line.product_uom_qty += 1
        self._deliver(self.contract, [serial])
        self.contract_line.invalidate_recordset()
