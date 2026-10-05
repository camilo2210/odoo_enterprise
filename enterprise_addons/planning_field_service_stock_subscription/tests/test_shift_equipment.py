from datetime import datetime

from odoo.tests import new_test_user

from .common import MaintenanceContractCommon


class TestShiftEquipment(MaintenanceContractCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.planner = new_test_user(cls.env, login='shift_planner', groups='planning.group_planning_manager')

    def _plan(self, partner=None, sale_line=None, user=None):
        return self.env['planning.slot'].with_user(user or self.env.user).create({
            'start_datetime': datetime(2026, 1, 5, 8, 0),
            'end_datetime': datetime(2026, 1, 5, 12, 0),
            'partner_id': (partner or self.customer).id,
            'sale_line_id': sale_line.id if sale_line else False,
        })

    def test_maintenance_contracts_follow_the_equipment_feature(self):
        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.group_field_service_allow_maintenance_contract,
                        "The setup enables maintenance contracts.")

        settings.group_field_service_allow_equipment = False
        settings._onchange_group_field_service_allow_equipment()
        self.assertFalse(settings.group_field_service_allow_maintenance_contract,
                         "Maintenance contracts are about equipment, they cannot outlive the feature.")

    def test_shift_on_a_contract_lists_its_equipment(self):
        self.contract_line.lot_ids = self.lot_1
        shift = self._plan(sale_line=self.contract_line)
        self.assertEqual(shift.lot_ids, self.lot_1,
                         "A shift planned on a contract should only list the equipment it covers.")

    def test_the_contract_prefill_needs_the_maintenance_contracts_setting(self):
        """ Without that setting a shift knows nothing about contracts. """
        self.contract_line.lot_ids = self.lot_1
        self.env['res.config.settings'].create({
            'group_field_service_allow_maintenance_contract': False,
        }).execute()
        self.assertFalse(
            self.env.user.has_group('planning_field_service_stock_subscription.group_field_service_allow_maintenance_contract'))

        shift = self._plan(sale_line=self.contract_line)
        self.assertEqual(shift.lot_ids, self.lot_1 + self.lot_2,
                         "The notebook should fall back on every piece of equipment the customer owns.")

    def test_shift_without_a_contract_lists_everything_the_customer_owns(self):
        shift = self._plan()
        self.assertEqual(shift.lot_ids, self.lot_1 + self.lot_2,
                         "Without a contract line, the notebook keeps listing the customer's equipment.")

    def test_shift_on_a_line_without_equipment_falls_back_on_the_customer(self):
        consultancy_line = self.env['sale.order.line'].create({
            'order_id': self.contract.id,
            'product_id': self.consultancy.id,
            'product_uom_qty': 1,
        })
        shift = self._plan(sale_line=consultancy_line)
        self.assertEqual(shift.lot_ids, self.lot_1 + self.lot_2,
                         "A line covering no equipment should not empty the notebook.")

    def test_the_contract_wins_over_a_hand_picked_subset(self):
        shift = self._plan(sale_line=self.contract_line)
        shift.lot_ids = self.lot_1

        self.contract_line.lot_ids = self.lot_1 + self.lot_2
        self.assertEqual(shift.lot_ids, self.lot_1 + self.lot_2,
                         "Changing what the contract covers re-derives the notebook.")

    def test_equipment_leaving_the_contract_resets_the_shift(self):
        shift = self._plan(sale_line=self.contract_line)
        shift.lot_ids = self.lot_1

        self.contract_line.lot_ids = self.lot_2
        self.assertEqual(shift.lot_ids, self.lot_2,
                         "Equipment that left the contract should leave the shift as well.")

    def test_planning_without_inventory_rights(self):
        """ 'sale.order.line.lot_ids' is Inventory data, planning a shift is not. """
        self.assertFalse(self.planner.has_group('stock.group_stock_user'),
                         "This test is about a planner who is not an Inventory user.")
        self.contract_line.lot_ids = self.lot_1
        shift = self._plan(sale_line=self.contract_line, user=self.planner)
        self.assertEqual(shift.sudo().lot_ids, self.lot_1,
                         "A planner should be able to plan on a contract without Inventory rights.")

        shift.with_user(self.planner)._compute_lot_ids()
        self.assertEqual(shift.sudo().lot_ids, self.lot_1,
                         "Refreshing the notebook should not ask for Inventory rights either.")

    def test_shift_is_under_warranty_while_the_contract_runs(self):
        shift = self._plan(sale_line=self.contract_line)
        self.assertTrue(shift.under_warranty,
                        "A shift planned on a running contract is covered by it.")

        self.contract.set_close()
        later_shift = self._plan(sale_line=self.contract_line)
        self.assertFalse(later_shift.under_warranty,
                         "Once the contract is closed, a new shift is no longer covered.")

    def test_shift_off_contract_is_not_under_warranty(self):
        self.assertFalse(self._plan().under_warranty,
                         "A shift planned outside any contract is not covered.")
