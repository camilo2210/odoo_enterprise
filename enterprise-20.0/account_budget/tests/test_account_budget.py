# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from freezegun import freeze_time

from .common import TestAccountBudgetCommon
from odoo.fields import Command
from odoo.tests import tagged
from itertools import product


@tagged('post_install', '-at_install')
class TestAccountBudget(TestAccountBudgetCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_account_budget(self):

        budget = self.budget_analytic_revenue

        self.assertRecordValues(budget, [{'state': 'draft'}])

        # I pressed the confirm button to confirm the Budget
        # Performing an action confirm on module budget.analytic
        budget.action_budget_confirm()

        # I check that budget is in "Confirmed" state
        self.assertRecordValues(budget, [{'state': 'confirmed'}])

        # I pressed the validate button to validate the Budget
        # Performing an action validate on module budget.analytic
        budget.action_budget_confirm()

        # I check that budget is in "Validated" state
        self.assertRecordValues(budget, [{'state': 'confirmed'}])

        # I pressed the revise button to set the Budget to "Revised" state
        # Performing an action revise on module budget.analytic
        budget.create_revised_budget()

        revised_budget = self.env['budget.analytic'].search([('parent_id', '=', budget.id)])
        self.assertTrue(revised_budget, "The revised budget should have been created")

        # I pressed the confirm button to confirm the Budget
        # Performing an action confirm on module budget.analytic
        revised_budget.action_budget_confirm()

        # I check that revised_budget is in "Confirmed" state and budget is in "Revised" state
        self.assertRecordValues(revised_budget, [{'state': 'confirmed'}])
        self.assertRecordValues(budget, [{'state': 'revised'}])

        # I pressed the done button to set the Revised Budget to "Done" state
        # Performing an action done on module budget.analytic
        revised_budget.action_budget_done()

        # I check that revised_budget is in "Done" state
        self.assertRecordValues(revised_budget, [{'state': 'done'}])

    def test_budget_split(self):
        # I created a budget split wizard with a date range and a period and a list of analytic plans
        res = self.env['budget.split.wizard'].create({
            'date_from': '2019-01-01',
            'date_to': '2019-12-31',
            'period': 'month',
            'analytical_plan_ids': [(6, 0, self.analytic_plan_projects.ids + self.analytic_plan_departments.ids)]
        }).action_budget_split()
        self.assertTrue(res.get('domain'), "The budget split wizard should have created and returned a domain of budget.line records")
        budget_lines = self.env['budget.line'].search(res.get('domain'))
        account_dict = {rec._column_name(): rec.account_ids.ids for rec in self.analytic_plan_projects + self.analytic_plan_departments}
        account_combinations = [dict(zip(account_dict.keys(), combination)) for combination in product(*account_dict.values())]
        for line, combination in zip(budget_lines, account_combinations):
            for column in combination:
                self.assertEqual(line[column].id, combination[column], "The budget line should have the correct accounts set")

    @freeze_time('2024-01-15 14:30:00')
    def test_revised_budget_name_generation(self):
        """Test that revised budget names are generated correctly."""
        budget = self.budget_analytic_revenue  # Use existing budget from setup
        budget.action_budget_confirm()

        revised_budget = budget.create_revised_budget()
        revised_budget = self.env['budget.analytic'].browse(revised_budget['res_id'])

        expected_name = f"{budget.name} - REV(2024-01-15 14:30)"
        self.assertEqual(revised_budget.name, expected_name)

    def test_budget_report_includes_assets(self):
        """ Test that 'asset_fixed' is included in an 'expense' budget report. """

        expense_account = self.company_data['default_account_expense']
        asset_account = self.company_data['default_account_assets']
        revenue_account = self.company_data['default_account_revenue']

        # Create a strictly "expense" budget
        budget_expense = self.env['budget.analytic'].create({
            'name': 'Test Expense Budget',
            'budget_type': 'expense',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })

        budget_line_expense = self.env['budget.line'].create({
            'budget_analytic_id': budget_expense.id,
            self.project_column_name: self.analytic_account_partner_a.id,
        })

        # Generate the journal entry hitting all three accounts
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2026-03-01',
            'line_ids': [
                Command.create({
                    'account_id': expense_account.id,
                    'debit': 100,
                    'analytic_distribution': {str(self.analytic_account_partner_a.id): 100},
                }),
                Command.create({
                    'account_id': asset_account.id,
                    'debit': 200,
                    'analytic_distribution': {str(self.analytic_account_partner_a.id): 100},
                }),
                Command.create({
                    'account_id': revenue_account.id,
                    'credit': 300,
                    'analytic_distribution': {str(self.analytic_account_partner_a.id): 100},
                }),
            ]
        })
        move.action_post()

        # The committed/achieved amounts should include both the expense and asset accounts: 100 + 200
        # Previously, these amounts would have been only 100 (the expense account)
        self.assertBudgetLine(budget_line_expense, achieved=300)

    def test_move_link_with_budget(self):
        """
        Test that the links between moves and budgets are correct
        """
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'line_ids': [Command.create({
                'quantity': 1.0,
                'price_unit': 100,
                'analytic_distribution': {str(self.analytic_account_partner_a.id): 100},
            })],
        })
        move.action_post()

        self.assertEqual(move.budget_analytic_ids, (self.budget_analytic_expense + self.budget_analytic_revenue + self.budget_analytic_both))

        analytic_account = self.env['account.analytic.account'].create({
            'name': 'analytic account',
            'partner_id': self.partner_a.id,
            'plan_id': self.analytic_plan_projects.id,
        })
        move2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'line_ids': [Command.create({
                'quantity': 1.0,
                'price_unit': 100,
                'analytic_distribution': {str(analytic_account.id): 100},
            })],
        })
        move2.action_post()
        self.assertFalse(move2.budget_analytic_ids)

        budget = self.env['budget.analytic'].create({
            'name': 'Budget test',
            'date_from': '2019-01-01',
            'date_to': '2019-12-31',
            'budget_type': 'both',
            'state': 'draft',
            'user_id': self.env.ref('base.user_admin').id,
            'budget_line_ids': [
                Command.create({
                    'budget_amount': 3500,
                    self.project_column_name: analytic_account.id,
                }),
            ],
        })
        move2.invalidate_recordset(['budget_analytic_ids'])
        self.assertEqual(move2.budget_analytic_ids, budget)

    def test_budget_report_analytic_filter(self):
        self.env['account.analytic.line'].create({
            'name': 'test aal',
            'date': '2019-06-01',
            self.project_column_name: self.analytic_account_partner_a.id,
            'amount': 100,
        })
        result = self.env['budget.report'].formatted_read_grouping_sets(
            domain=[
                ('budget_analytic_id', '=', self.budget_analytic_revenue.id),
                ('budget_line_id', 'in', self.budget_analytic_revenue.budget_line_ids.ids),
            ],
            grouping_sets=[['budget_analytic_id', 'budget_line_id']],
            aggregates=['budget:sum', 'achieved:sum'],
        )
        rows = result[0]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row['budget_analytic_id'][0], self.budget_analytic_revenue.id)
        self.assertEqual(sum(row['budget:sum'] for row in rows), 55000.0)
        self.assertEqual(sum(row['achieved:sum'] for row in rows), 100.0)
