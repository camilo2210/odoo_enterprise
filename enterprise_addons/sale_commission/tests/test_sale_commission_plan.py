# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import freeze_time, tagged
from odoo.addons.sale_commission.tests.test_sale_commission_common import TestSaleCommissionCommon


@tagged('post_install', '-at_install')
class TestSaleCommissionPlan(TestSaleCommissionCommon):

    _test_user_groups = None  # FIXME list needed groups

    @freeze_time("2024-01-15")
    def test_targets_preserved_when_extending_date_range(self):
        """ Test that existing targets are preserved when extending the plan's date range. """
        plan = self.env['sale.commission.plan'].create({
            'name': "Test Plan 2024",
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
            'periodicity': 'quarter',
        })
        self.assertEqual(len(plan.target_ids), 4, "Should have 4 quarterly targets for 2024.")

        # Set custom amounts to simulate user configuration.
        plan.target_ids[0].amount = 10000
        plan.target_ids[1].amount = 15000
        plan.target_ids[2].amount = 12000
        plan.target_ids[3].amount = 18000

        # Extend the plan to 2025.
        plan.date_to = '2025-12-31'

        # Verify: 2024 targets preserved with amounts, 2025 targets added.
        self.assertEqual(len(plan.target_ids), 8, "Should have 8 targets total (4 for 2024 + 4 for 2025).")
        targets_2024 = plan.target_ids.filtered(lambda t: t.date_from.year == 2024).sorted('date_from')
        self.assertEqual(len(targets_2024), 4, "Should still have 4 targets for 2024.")
        self.assertEqual(targets_2024[0].amount, 10000, "Q1 2024 target amount should be preserved.")
        self.assertEqual(targets_2024[1].amount, 15000, "Q2 2024 target amount should be preserved.")
        self.assertEqual(targets_2024[2].amount, 12000, "Q3 2024 target amount should be preserved.")
        self.assertEqual(targets_2024[3].amount, 18000, "Q4 2024 target amount should be preserved.")

        targets_2025 = plan.target_ids.filtered(lambda t: t.date_from.year == 2025)
        self.assertEqual(len(targets_2025), 4, "Should have 4 new targets for 2025.")
        self.assertTrue(all(t.amount == 0 for t in targets_2025), "New 2025 targets should have default amount 0.")

    @freeze_time("2024-01-15")
    def test_targets_removed_when_shortening_date_range(self):
        """ Test that targets outside the new range are removed when shortening the plan. """
        plan = self.env['sale.commission.plan'].create({
            'name': "Test Plan 2024",
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
            'periodicity': 'quarter',
        })
        self.assertEqual(len(plan.target_ids), 4, "Should have 4 quarterly targets for 2024.")

        # Shorten to first half of 2024.
        plan.date_to = '2024-06-30'

        # Only Q1 and Q2 should remain.
        self.assertEqual(len(plan.target_ids), 2, "Should only have 2 targets after shortening to H1 2024.")
        self.assertEqual(plan.target_ids.sorted('date_from')[0].name, '2024 Q1', "First target should be Q1 2024.")
        self.assertEqual(plan.target_ids.sorted('date_from')[1].name, '2024 Q2', "Second target should be Q2 2024.")

    def test_unrelated_targets_removed_when_updating_periodicity(self):
        """ Test that the targets of a commission plan are properly removed if they don't belong to the new periodicity set. """
        plan = self.env['sale.commission.plan'].create({
            'name': 'Test Plan',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'periodicity': 'year',
        })
        self.assertEqual(len(plan.target_ids), 1)
        plan.periodicity = 'quarter'
        self.assertEqual(len(plan.target_ids), 4)
        plan.periodicity = 'month'
        self.assertEqual(len(plan.target_ids), 12)
