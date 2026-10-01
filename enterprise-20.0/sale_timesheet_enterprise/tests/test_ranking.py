# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo.addons.sale_timesheet.tests.common import TestCommonSaleTimesheet
from odoo.tests import tagged


@tagged('-at_install', 'post_install')
class TestSaleTimesheetEnterpriseRanking(TestCommonSaleTimesheet):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.period_start = datetime(2023, 4, 1, 7, 0, 0)
        cls.period_end = datetime(2023, 4, 30, 18, 0, 0)
        cls.so = cls.env['sale.order'].create({
            'company_id': cls.employee_user.company_id.id,
            'partner_id': cls.partner_a.id,
            'partner_invoice_id': cls.partner_a.id,
            'partner_shipping_id': cls.partner_a.id,
        })
        cls.sol = cls.env['sale.order.line'].create({
            'product_id': cls.product_order_timesheet3.id,
            'product_uom_qty': 10,
            'order_id': cls.so.id,
        })
        cls.project_billable = cls.env['project.project'].create({
            'name': 'Billable project',
            'sale_line_id': cls.sol.id,
            'allow_billable': True,
        })
        cls.task_billable = cls.env['project.task'].create({
            'name': 'Billable Task',
            'sale_line_id': cls.sol.id,
            'project_id': cls.project_billable.id,
        })
        cls.employee_user.billable_time_target = 160
        cls.env['res.config.settings'].create({'timesheet_show_rates': True, 'timesheet_show_leaderboard': True}).execute()

    def test_get_timesheet_ranking_data_with_timesheet_show_rates_disabled(self):
        self.env['res.config.settings'].create({'timesheet_show_rates': False, 'timesheet_show_leaderboard': False}).execute()
        self.assertFalse(
            self.env['res.company'].get_timesheet_ranking_data(self.period_start, self.period_end, True),
            "An empty dict should be returned since the feature is disabled on the company."
        )

    def test_get_timesheet_ranking_data_with_timesheet_show_leaderboard_disabled(self):
        self.env['res.config.settings'].create({'timesheet_show_leaderboard': False}).execute()
        self.assertFalse(
            self.env['res.company'].get_timesheet_ranking_data(self.period_start, self.period_end, True),
            "An empty dict should be returned since the feature is disabled on the company."
        )

    def test_get_timesheet_ranking_data_with_single_line(self):
        self.employee_user.user_id = self.env.user
        self.env['account.analytic.line'].create({
            'employee_id': self.employee_user.id,
            'unit_amount': 8,
            'date': datetime(2023, 4, 15, 7, 0, 0, 0),
            'project_id': self.project_billable.id,
            'task_id': self.task_billable.id,
        })
        data = self.env['res.company'].get_timesheet_ranking_data(self.period_start, self.period_end, True)
        self.assertTrue(data)
        self.assertTrue(data['leaderboard'])
        self.assertEqual(len(data['leaderboard']), 1)
        self.assertDictEqual(data['leaderboard'][0], {
            'id': self.employee_user.id,
            'name': self.employee_user.name,
            'billable_time_target': self.employee_user.billable_time_target,
            'billable_time': 0.0,
            'total_time': 8.0,
            'billing_rate': 0.0,
        })

    def test_fetch_tip(self):
        """ This test will check that a tip is actually returned when calling get_timesheet_ranking_data() with fetch_tip parameter set to true. """
        data = self.company_data['company'].get_timesheet_ranking_data(self.period_start, self.period_end, True)
        self.assertTrue(data.get('tip'), 'A tip should be set in the company\'s timesheet ranking data.')

    def test_total_time(self):
        """ This test will check that the user's total time and total valid time in their ranking is correct. For
        example if the user has timesheeted in the future, this time is invalidated and excluded in the total valid
        time calculation. The total time is the same except there is no invalidation system based on the time.
        """
        self.env['account.analytic.line'].create({
            'employee_id': self.employee_user.id,
            'unit_amount': 8,
            'date': datetime(2023, 4, 15, 7, 0, 0, 0),  # before self.today
            'project_id': self.project_billable.id,
            'task_id': self.task_billable.id,
        })
        ranking_data = self.employee_user.company_id.get_timesheet_ranking_data(self.period_start, self.period_end, False)
        self.assertEqual(ranking_data['leaderboard'][0]['total_time'], 8.0, 'The employee\'s total time should be 8.')

        self.env['account.analytic.line'].create({
            'employee_id': self.employee_user.id,
            'unit_amount': 8,
            'date': datetime(2023, 4, 26, 7, 0, 0, 0),  # after self.today
            'project_id': self.project_billable.id,
            'task_id': self.task_billable.id,
        })
        ranking_data = self.employee_user.company_id.get_timesheet_ranking_data(self.period_start, self.period_end, False)
        self.assertEqual(ranking_data['leaderboard'][0]['total_time'], 16.0, 'The employee\'s total time should be 16.')

    def test_billing_rate(self):
        # Add a first timesheet with 50% of the billable_time_target
        self.env['account.analytic.line'].create({
            'employee_id': self.employee_user.id,
            'unit_amount': 80,
            'date': datetime(2023, 4, 15, 7, 0, 0, 0),
            'project_id': self.project_billable.id,
            'task_id': self.task_billable.id,
            'billable_type': '04_billable_time',
        })
        data = self.env['res.company'].get_timesheet_ranking_data(self.period_start, self.period_end, False)
        self.assertDictEqual(data['leaderboard'][0], {
            'id': self.employee_user.id,
            'name': self.employee_user.name,
            'billable_time_target': self.employee_user.billable_time_target,
            'billable_time': 80.0,
            'total_time': 80.0,
            'billing_rate': 50.0,
        })

        # Add another timesheet with the other 50% of the billable_time_target
        self.env['account.analytic.line'].create({
            'employee_id': self.employee_user.id,
            'unit_amount': 80,
            'date': datetime(2023, 4, 27, 7, 0, 0, 0),
            'project_id': self.project_billable.id,
            'task_id': self.task_billable.id,
            'billable_type': '04_billable_time',
        })
        data = self.env['res.company'].get_timesheet_ranking_data(self.period_start, self.period_end, False)
        self.assertDictEqual(data['leaderboard'][0], {
            'id': self.employee_user.id,
            'name': self.employee_user.name,
            'billable_time_target': self.employee_user.billable_time_target,
            'billable_time': 160.0,
            'total_time': 160.0,
            'billing_rate': 100.0,  # Billing rate increases to 100%
        })
