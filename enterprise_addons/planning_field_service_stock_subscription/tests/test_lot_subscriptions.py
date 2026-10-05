from odoo import Command
from odoo.tests import new_test_user

from .common import MaintenanceContractCommon


class TestLotSubscriptions(MaintenanceContractCommon):
    def test_lot_lists_the_contract_covering_it(self):
        self.assertEqual(self.lot_1.subscription_ids, self.contract, "A machine should list the subscription sold along with it.")
        self.assertEqual(self.lot_1.subscriptions_count, 1, "The stat button should count that subscription.")

    def test_a_plain_sales_order_is_not_a_contract(self):
        """ A one shot intervention on the machine is not a maintenance contract. """
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({'product_id': self.consultancy.id, 'product_uom_qty': 1})],
        })
        order.action_confirm()
        order.order_line.lot_ids = self.lot_1
        self.lot_1.invalidate_recordset()

        self.assertFalse(order.is_subscription, "An order without a plan is not a subscription.")
        self.assertNotIn(order, self.lot_1.subscription_ids, "Only subscriptions should be listed as maintenance contracts.")

    def test_another_customers_contract_is_not_listed(self):
        other_contract = self._sell_machines_under_contract(self.other_customer, ['SN-OTHER'])
        other_lot = other_contract.order_line.lot_ids
        self.assertEqual(other_lot.subscription_ids, other_contract, "The other customer's machine lists the other customer's contract.")
        self.assertNotIn(other_contract, self.lot_1.subscription_ids, "A machine should never list a contract belonging to another customer.")

    def test_a_running_contract_is_maintained(self):
        self.assertEqual(self.contract.subscription_state, '3_progress', "A confirmed subscription is running.")
        self.assertTrue(self.lot_1.is_maintained, "A machine covered by a running contract is maintained.")

    def test_a_closed_contract_no_longer_maintains(self):
        self.contract.set_close()
        self.lot_1.invalidate_recordset()
        self.assertEqual(self.contract.subscription_state, '6_churn', "'6_churn' is the state a closed subscription lands in.")
        self.assertFalse(self.lot_1.is_maintained, "Once the contract is closed the machine is no longer maintained.")

    def test_one_running_contract_out_of_two_still_maintains(self):
        second_contract = self._sell_machines_under_contract(self.customer, ['SN-SECOND'])
        second_contract.order_line.filtered(
            lambda line: line.product_id == self.maintenance
        ).lot_ids = self.lot_1
        second_contract.set_close()
        self.lot_1.invalidate_recordset()

        self.assertEqual(self.lot_1.subscription_ids, self.contract + second_contract, "Both contracts cover that machine.")
        self.assertTrue(self.lot_1.is_maintained, "A single running contract is enough for the machine to be maintained.")

    def test_action_opens_the_only_contract(self):
        action = self.lot_1.action_view_subscriptions()
        self.assertEqual(action['res_id'], self.contract.id, "A machine covered by one contract opens it directly.")
        self.assertEqual(action['view_mode'], 'form')

    def test_action_lists_several_contracts(self):
        second_contract = self._sell_machines_under_contract(self.customer, ['SN-THIRD'])
        second_contract.order_line.filtered(
            lambda line: line.product_id == self.maintenance
        ).lot_ids = self.lot_1
        self.lot_1.invalidate_recordset()

        action = self.lot_1.action_view_subscriptions()
        self.assertFalse(action.get('res_id'), "A machine covered by several contracts opens a list instead.")
        self.assertEqual(action['domain'], [('id', 'in', (self.contract + second_contract).ids)])

    def test_read_without_sales_nor_inventory_rights(self):
        """ Opening a serial number reads 'is_maintained', which digs into sales data. """
        planner = new_test_user(self.env, login='lot_planner', groups='planning.group_planning_user')
        self.assertFalse(planner.has_group('sales_team.group_sale_salesman'))
        self.assertFalse(planner.has_group('stock.group_stock_user'))

        lot = self.lot_1.with_user(planner)
        lot.invalidate_recordset()
        self.assertTrue(lot.is_maintained, "A planning user must be able to open a machine without Sales nor Inventory rights.")
