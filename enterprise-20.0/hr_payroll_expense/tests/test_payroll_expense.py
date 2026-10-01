# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import UserError
from odoo.addons.hr_expense.tests.common import TestExpenseCommon
from odoo.addons.hr_payroll_account.tests.test_hr_payroll_account import TestHrPayrollAccountCommon


@tagged('post_install', '-at_install')
class TestPayrollExpense(TestHrPayrollAccountCommon, TestExpenseCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company_data['company'].id]))
        cls.company.tax_calculation_rounding_method = 'round_per_line'

        cls.payslip_run.company_id = cls.company_data['company'].id

        # Else the payslip_run will be using the the demo company in its environment, thus raising an error
        # when payslip_run.action_validate() is called. Because the demo company doesn't have a journal
        # and payslip_run.slip_ids.journal_id is company dependent
        cls.payslip_run.env = cls.env

        cls.expense_employee.update({
            'sex': 'male',
            'birthday': '1984-05-01',
            'company_id': cls.company_data['company'].id,
            'country_id': cls.company_data['company'].country_id.id,
            'department_id': cls.dep_rd.id,
            'date_version': cls.frozen_today - relativedelta(years=2),
            'contract_date_start': cls.frozen_today - relativedelta(years=2),
            'contract_date_end': cls.frozen_today + relativedelta(years=2),
            'wage': 5000.33,
            'structure_type_id': cls.hr_structure_type.id,
        })
        cls.expense_contract = cls.expense_employee.version_id
        expense_payslip_tax_account = cls.env['account.account'].create({
                'name': 'Rental Tax',
                'code': '777777',
                'account_type': 'asset_current',
            })
        expense_tax = cls.env['account.tax'].create({
            'name': "Some taxes on normal payslip",
            'amount_type': 'percent',
            'amount': 10.0,
            'type_tax_use': 'sale',
            'company_id': cls.company_data['company'].id,
            'invoice_repartition_line_ids': [
                Command.create({'factor_percent': 100, 'repartition_type': 'base'}),
                Command.create({'factor_percent': 100, 'account_id': expense_payslip_tax_account.id}),
            ],
            'refund_repartition_line_ids': [
                Command.create({'factor_percent': 100, 'repartition_type': 'base'}),
                Command.create({'factor_percent': 100, 'account_id': expense_payslip_tax_account.id}),
            ],
        })
        test_account = cls.env['account.account'].create({
                'name': 'House Rental',
                'code': '654321',
                'account_type': 'income',
                'tax_ids': [Command.link(expense_tax.id)],
        })
        cls.expense_payable_account = cls.env['account.account'].create({
                'name': 'payable',
                'code': '654323',
                'account_type': 'liability_payable',
            })
        cls.expense_payslip_journal = cls.env['account.journal'].create({
            'name': 'EXPENSE',
            'code': 'EXP',
            'type': 'general',
            'company_id': cls.company_data['company'].id,
            'default_account_id': cls.company_data['default_journal_cash'].default_account_id.id,
        })
        cls.expense_hr_structure = cls.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Software Developer',
            'journal_id': cls.expense_payslip_journal.id,
            'type_id': cls.env['hr.payroll.structure.type'].create({'name': 'Employee', 'country_id': False}).id,
            'rule_ids': [],
        })
        cls.expense_salary_rules = cls.env['hr.salary.rule'].create([
            {
                'name': 'Basic Salary',
                'amount_select': 'code',
                'amount_python_compute': 'result = version.wage',
                'code': 'BASIC',
                'category_ids': [(4, cls.env.ref('hr_payroll.BASIC').id)],
                'sequence': 1,
                'account_debit': test_account.id,
                'struct_ids': [Command.link(cls.expense_hr_structure.id)],
            }, {
                'name': 'House Rent Allowance',
                'amount_select': 'percentage',
                'amount_percentage': 40,
                'amount_percentage_base': 'version.wage',
                'code': 'HRA',
                'category_ids': [(4, cls.env.ref('hr_payroll.ALW').id)],
                'sequence': 5,
                'account_debit': test_account.id,
                'struct_ids': [Command.link(cls.expense_hr_structure.id)],
            }, {
                'name': 'Reimbursed Expenses',
                'code': 'EXPENSES',
                'sequence': 6,
                'condition_select': 'property_input',
                'amount_select': 'property_input',
                'input_usage_payslip': True,
                'appears_on_payslip': 'non_zero',
                'category_ids': [(4, cls.env.ref('hr_payroll.ALW').id)],
                'account_debit': cls.expense_payable_account.id,
                'struct_ids': [Command.link(cls.expense_hr_structure.id)],
            }, {
                'name': 'Reimbursed Expenses Non Payable Debit Account',
                'condition_select': 'property_input',
                'amount_select': 'property_input',
                'code': 'EXPENSES2',
                'category_ids': [Command.link(cls.env.ref('hr_payroll.ALW').id)],
                'sequence': 7,
                'input_usage_payslip': True,
                'appears_on_payslip': 'non_zero',
                'account_debit': test_account.id,
                'struct_ids': [Command.link(cls.expense_hr_structure.id)],
            }, {
                'name': 'Net Salary',
                'amount_select': 'code',
                'amount_python_compute': 'result = categories["BASIC"] + categories["ALW"] + categories["DED"]',
                'code': 'NET',
                'category_ids': [(4, cls.env.ref('hr_payroll.NET').id)],
                'sequence': 10,
                'account_credit': test_account.id,
                'struct_ids': [Command.link(cls.expense_hr_structure.id)],
            }])
        cls.expense_salary_rule = cls.expense_hr_structure.rule_ids.filtered(lambda rule: rule.code == 'EXPENSES')
        cls.product_c.salary_rule_ids = [Command.set([cls.expense_salary_rule.id])]
        cls.expense_employee.structure_id = cls.expense_hr_structure

    def create_payslip(self, vals=None):
        return self.env['hr.payslip'].create({
            'employee_id': self.expense_employee.id,
            'struct_id': self.expense_hr_structure.id,
            'version_id': self.expense_contract.id,
            'payslip_run_id': self.payslip_run.id,
            'date_from': self.frozen_today - relativedelta(months=1),
            'date_to': self.frozen_today,
            'company_id': self.company_data['company'].id,
            **(vals or {})
        })

    def get_reconciliation_lines_from_accounts(self, account_ids):
        """ Helper function to return reconciled lines linked to specific accounts """
        return self.env['account.partial.reconcile'].search([
            '|', ('debit_move_id.account_id', 'in', account_ids), ('credit_move_id.account_id', 'in', account_ids),
        ])

    @staticmethod
    def get_all_amls_to_be_reconciled(expenses, payslips, include_payslips_payment_terms_amls=False):
        """  Helper function to return all the amls required to test the reconciliation """

        expenses_amls = expenses.account_move_id.line_ids.filtered(lambda line: line.display_type == 'payment_term')

        payslip_payable_lines = payslips.move_id.line_ids.filtered(lambda line: line.account_type == 'liability_payable')
        if include_payslips_payment_terms_amls:
            return expenses_amls, payslip_payable_lines

        payslip_payment_terms = payslip_payable_lines.filtered(lambda line: line.display_type == 'payment_term')
        payslip_expense_lines = payslip_payable_lines - payslip_payment_terms
        return expenses_amls, payslip_expense_lines

    @freeze_time('2022-01-25')
    def test_main_flow_expense_in_payslip(self):
        expense_1 = self.create_expenses({'name': 'Expense', 'payment_mode': 'payslip_account'})
        expense_2 = self.create_expenses({
            'name': 'Expense 2',
            'total_amount_currency': 3000,
            'payment_mode': 'payslip_account',
        })
        expenses = expense_1 | expense_2
        expenses_total_amount = sum(expenses.mapped('total_amount'))
        expenses.action_submit()
        expenses.action_approve()

        # Creating payslip links the expense to the payslip
        payslip = self.create_payslip()
        self.assertRecordValues(expenses, [
            {'payslip_id': payslip.id, 'state': 'approved', 'account_move_id': False},
            {'payslip_id': payslip.id, 'state': 'approved', 'account_move_id': False},
        ])
        self.assertRecordValues(payslip, [
            {'expense_ids': expenses.ids, 'state': 'draft', 'employee_id': self.expense_employee.id},
        ])
        self.assertRecordValues(payslip.input_line_ids, [
            {'salary_rule_id': self.expense_salary_rule.id, 'amount': expenses_total_amount},
        ])

        # Test removing expense from payslip unlinks the two
        expense_1.action_remove_from_payslip()
        self.assertRecordValues(expenses, [
            {'name': 'Expense',   'state': 'approved', 'payslip_id': False,      'account_move_id': False},
            {'name': 'Expense 2', 'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
        ])
        self.assertRecordValues(payslip, [
            {'expense_ids': expense_2.ids, 'state': 'draft', 'employee_id': self.expense_employee.id},
        ])
        self.assertRecordValues(payslip.input_line_ids, [
            {'salary_rule_id': self.expense_salary_rule.id, 'amount': expense_2.total_amount},
        ])

        expense_2.action_remove_from_payslip()
        self.assertRecordValues(expenses, [
            {'state': 'approved', 'payslip_id': False, 'account_move_id': False},
            {'state': 'approved', 'payslip_id': False, 'account_move_id': False},
        ])
        self.assertRecordValues(payslip, [
            {'expense_ids': [], 'state': 'draft', 'employee_id': self.expense_employee.id},
        ])
        self.assertFalse(payslip.input_line_ids)

        # This should re-add the expense to the payslip
        expenses._report_in_next_payslip()
        payslip.action_payslip_draft()
        self.assertRecordValues(expenses, [
            {'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
            {'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
        ])

        # Moving up to setting the payslip as done shouldn't change anything for the expense
        self.payslip_run.slip_ids.compute_sheet()
        self.payslip_run.action_validate()
        self.assertRecordValues(expenses, [
            {'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
            {'state': 'approved', 'payslip_id': payslip.id, 'account_move_id': False},
        ])
        # Test trying to remove the expense from the payslip when a payslip has generated a move raises an error
        with self.assertRaises(UserError):
            expense_1.action_remove_from_payslip()
        with self.assertRaises(UserError):
            expense_1.action_reset()

        # Posting the payslip move should create and post the expense move
        payslip.move_id.action_post()
        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': expenses_total_amount, 'amount_residual': 0, 'payment_state': 'paid', 'state': 'posted'},
        ])
        self.assertRecordValues(expenses, [
            {'state': 'paid', 'payslip_id': payslip.id},
            {'state': 'paid', 'payslip_id': payslip.id},
        ])

        expenses_lines_to_reconcile, payslip_lines_to_reconcile = \
            self.get_all_amls_to_be_reconciled(expenses, payslip, include_payslips_payment_terms_amls=True)

        self.assertRecordValues(expenses_lines_to_reconcile.sorted('balance'), [
            {'balance': -expenses_total_amount},
        ])
        self.assertRecordValues(payslip_lines_to_reconcile, [
            {'balance': expenses_total_amount, 'account_id': self.expense_payable_account.id},
        ])
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expenses_lines_to_reconcile | payslip_lines_to_reconcile).account_id.ids
        )
        self.assertTrue(reconciliation_lines, "There should be automatic reconciliation lines as it's the most simple case")

        # Because the expense & the payslip moves don't have the same account, there should be a misc entry generated
        misc_move = reconciliation_lines.debit_move_id.move_id - (expenses.account_move_id | payslip.move_id)
        self.assertEqual(
            len(misc_move),
            1,
            "Because the expense & the payslip moves don't have the same account, there should be a misc entry generated",
        )

        misc_move_lines = misc_move.line_ids.sorted('balance')
        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': expenses_total_amount, 'debit_move_id': misc_move_lines.ids[1], 'credit_move_id': expenses_lines_to_reconcile.ids[0]},
            {'amount': expenses_total_amount, 'debit_move_id': payslip_lines_to_reconcile.id, 'credit_move_id': misc_move_lines.ids[0]},
        ])

        # Test reversing the payslip move keeps the expense linked to the payslip
        expense_move = expenses.account_move_id
        payslip.move_id.button_draft()
        payslip.move_id.unlink()
        self.assertRecordValues(expenses, [
            {'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_move.id},
            {'state': 'posted', 'payslip_id': payslip.id, 'account_move_id': expense_move.id},
        ])
        payslip.action_payslip_draft()
        payslip.unlink()
        self.assertRecordValues(expenses, [
            {'state': 'posted', 'payslip_id': False, 'account_move_id': expense_move.id},
            {'state': 'posted', 'payslip_id': False, 'account_move_id': expense_move.id},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_expense_with_expense_payslip_same_payable_account(self):
        """
        Test posting the payslip move, in the case where the payable account is the same for both the payslip & the expense moves
        """
        expense = self.create_expenses({'payment_mode': 'payslip_account'})
        expense.action_submit()
        expense.action_approve()

        self.assertRecordValues(expense, [
            {'total_amount': 1000.0, 'state': 'approved'},
        ])

        # Sets the expense rule on the payroll expense rule
        self.expense_salary_rule.account_debit = expense._get_expense_account_destination()

        payslip = self.create_payslip()
        self.assertEqual(
            1000.0,
            payslip._get_input_line_amount('EXPENSES'),
            "The expense total amount should be added to the new payslip expense input line",
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()
        # Posting the payslip move should create and post expense move
        payslip.move_id.action_post()
        self.assertRecordValues(expense.account_move_id, [
            {'amount_total': 1000.0, 'amount_residual': 0, 'payment_state': 'paid', 'state': 'posted'},
        ])

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        expense_line_to_reconcile, payslip_line_to_reconcile = self.get_all_amls_to_be_reconciled(expense, payslip)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([expense._get_expense_account_destination()])

        misc_move = reconciliation_lines.debit_move_id.move_id - (expense.account_move_id | payslip.move_id)
        self.assertFalse(
            misc_move,
            "Because the expense & the payslip moves have the same account, there should be no misc entry generated",
        )

        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': 1000.0, 'debit_move_id': payslip_line_to_reconcile.id, 'credit_move_id': expense_line_to_reconcile.id},
        ])

    @freeze_time('2022-01-25')
    def test_corner_case_expense_with_all_identical_payable_accounts(self):
        """
        Similar case than `test_corner_case_expense_with_expense_payslip_same_payable_account`
        except that the payslip payment term account is also the same
        """
        expense = self.create_expenses({'payment_mode': 'payslip_account'})
        expense.action_submit()
        expense.action_approve()

        self.assertRecordValues(expense, [
            {'total_amount': 1000.0, 'state': 'approved'},
        ])

        # Sets the expense rule on the payroll expense rule & NET rule
        self.expense_salary_rule.account_debit = expense._get_expense_account_destination()
        net_rule = self.expense_hr_structure.rule_ids.filtered(lambda rule: rule.code == 'NET')
        net_rule.account_credit = expense._get_expense_account_destination()

        payslip = self.create_payslip()
        self.assertEqual(
            1000.0,
            payslip._get_input_line_amount('EXPENSES'),
            "The expense total amount should be added to the new payslip expense input line",
        )
        payslip.compute_sheet()
        payslip.action_payslip_done()
        # Posting the payslip move should create and post expense move
        payslip.move_id.action_post()
        self.assertRecordValues(expense.account_move_id, [
            {'amount_total': 1000.0, 'amount_residual': 0.0, 'payment_state': 'paid', 'state': 'posted'},
        ])

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([expense._get_expense_account_destination()])

        misc_move = reconciliation_lines.debit_move_id.move_id - (expense.account_move_id | payslip.move_id)
        self.assertFalse(
            misc_move,
            "Because the expense & the payslip moves have the same account, there should be no misc entry generated",
        )

        expense_line_to_reconcile, payslip_line_to_reconcile = \
            self.get_all_amls_to_be_reconciled(expense, payslip, include_payslips_payment_terms_amls=True)

        payslip_line_reconciled = payslip_line_to_reconcile.filtered('reconciled')
        self.assertEqual(len(payslip_line_reconciled), 1, "Only one line should be reconciled")
        self.assertEqual(
            payslip_line_reconciled.name,
            'Reimbursed Expenses',
            'The expected Expense line should be the one that is reconciled',
        )

        self.assertRecordValues(reconciliation_lines.sorted('amount'), [
            {'amount': 1000.0, 'debit_move_id': payslip_line_reconciled.id, 'credit_move_id': expense_line_to_reconcile.id},
        ])

    @freeze_time('2022-01-25')
    def test_expense_payslip_with_existing_bill(self):
        """
        Test flow for expense paid by employee, with an existing bill and refund on payslip
        """
        # Create the existing bill
        partner = self.env['res.partner'].create({'name': 'test supplier'})
        bill = self.env['account.move'].create({
            'partner_id': partner.id,
            'move_type': 'in_invoice',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'company_id': self.env.company.id,
            'date': '2022-01-01',
            'invoice_date': '2022-01-01',
            'invoice_line_ids': [Command.create({
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 100,
            })]
        })

        # Create expense for the same amount as the bill
        expense = self.create_expenses({
            'name': 'Expense',
            'payment_mode': 'payslip_account',
            'vendor_id': partner.id,
            'total_amount_currency': bill.amount_total,
            'has_existing_bill': True,
            'existing_bill_id': bill.id,
        })
        expense.action_submit()
        expense.action_approve()
        self.assertTrue(expense.refund_in_payslip)

        # Should have created a debt transfer entry, and the existing bill should have been marked as paid
        payable_line = bill.line_ids.filtered(lambda line: line.account_type == 'liability_payable')
        account_id = payable_line.account_id.id
        expense_move = expense.account_move_id
        expected_expense_move_lines = [
            {'account_id': account_id, 'balance': 100.0, 'reconciled_lines_ids': payable_line.ids},
            {'account_id': self.expense_payable_account.id, 'balance': -100.0, 'reconciled_lines_ids': []},
        ]
        self.assertRecordValues(expense_move.line_ids, expected_expense_move_lines)
        self.assertEqual(bill.payment_state, 'paid')
        self.assertEqual(expense.state, 'approved')

        # Create the payslip and draft and unlink expense move
        payslip = self.create_payslip()
        self.assertEqual(expense.payslip_id.id, payslip.id)
        expense.account_move_id.button_draft()
        expense.account_move_id.unlink()
        self.assertRecordValues(expense, [{
            'payslip_id': False,
            'refund_in_payslip': False,
        }])

        # Approve expense and validate payslip
        expense.action_approve()
        payslip.action_payslip_draft()
        self.payslip_run.slip_ids.compute_sheet()
        self.payslip_run.action_validate()
        payslip.move_id.action_post()

        # Should have reconciled the expense move with the payslip move
        expected_expense_move_lines[-1]['reconciled_lines_ids'] = [payslip.move_id.line_ids.filtered(lambda l: l.account_id == self.expense_payable_account).id]
        expense_move = expense.account_move_id
        self.assertRecordValues(expense_move.line_ids, expected_expense_move_lines)
        self.assertEqual(expense.state, 'posted')

        # Finally, pay the salary -> the expense is marked as paid
        payslip.action_payslip_paid()
        self.assertEqual(expense.state, 'paid')

    @freeze_time('2022-01-25')
    def test_corner_case_expense_edited_expense_move(self):
        """
        Test that, as you can edit the expense account move independently of the expense, it will still prepare the reconciliation if the
        totals do not match (as it would require a write-off misc move & user input to select a write-off account)
        """
        expenses = self.create_expenses([
            {
                'name': 'Expense To Keep',
                'employee_id': self.expense_employee.id,
                'payment_mode': 'payslip_account',
                'product_id': self.product_c.id,
                'total_amount_currency': 1000.00,
                'tax_ids': [Command.set(self.tax_purchase_a.ids)],
                'date': '2022-01-26',
                'company_id': self.company_data['company'].id,
                'currency_id': self.company_data['currency'].id,
            },
            {
                'name': 'Expense To Edit',
                'employee_id': self.expense_employee.id,
                'payment_mode': 'payslip_account',
                'product_id': self.product_c.id,
                'total_amount_currency': 2000.00,
                'tax_ids': [Command.set(self.tax_purchase_a.ids)],
                'date': '2022-01-25',
                'company_id': self.company_data['company'].id,
                'currency_id': self.company_data['currency'].id,
            },
        ])
        expenses.action_submit()
        expenses.action_approve()
        expenses._post_without_wizard_payslip_mode()

        self.assertRecordValues(expenses, [
            {'total_amount': 1000.0, 'state': 'posted'},
            {'total_amount': 2000.0, 'state': 'posted'},
        ])
        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': 3000.0, 'amount_residual': 3000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        # Edit the total_amount on the expense move by duplicating the product line
        line_to_duplicate = expenses.account_move_id.line_ids.filtered(lambda line: 'Expense To Edit' in (line.name or ""))[:1]
        line_to_duplicate.move_id.button_draft()
        line_to_duplicate.copy()
        line_to_duplicate.move_id.action_post()

        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': 5000.0, 'amount_residual': 5000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        payslip = self.create_payslip()
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self.assertEqual(
            3000,
            payslip._get_input_line_amount('EXPENSES'),
            "The expenses total amount should be added to the new payslip expense input line",
        )
        payslip.move_id.action_post()

        # Check the two moves are NOT reconciled
        # Get the corresponding account.partial.reconcile lines
        expense_lines_to_reconcile, payslip_line_to_reconcile = self.get_all_amls_to_be_reconciled(expenses, payslip)
        reconciliation_lines = self.get_reconciliation_lines_from_accounts(
            (expense_lines_to_reconcile | payslip_line_to_reconcile).account_id.ids
        )
        self.assertFalse(
            reconciliation_lines,
            "Because the expense & the payslip moves don't have the same amount, there should be no reconciliation",
        )
        self.assertRecordValues(expenses, [
            {'state': 'posted'},
            {'state': 'posted'},
        ])
        self.assertRecordValues(expenses.account_move_id, [
            {'payment_state': 'not_paid', 'amount_residual': 5000.00},
        ])

        self.assertSequenceEqual(
            [f'I0000000000-{payslip.move_id.id}-{min(expenses.account_move_id.ids)}'] * 2,
            [*expense_lines_to_reconcile.mapped('matching_number'), payslip_line_to_reconcile.matching_number],
            "A temporary matching number should still be present on the account move lines to help manually reconcile them"
        )

    def test_already_paid_expense(self):
        """
         Test that you can post the move of your payslip, even if the expense has been flagged to be reimbursed through a payslip,
         but still got paid the "common way"
         """
        paid_or_in_payment_state = self.env['account.move']._get_invoice_in_payment_state()

        expense_paid_before_payslip_creation = self.create_expenses({'payment_mode': 'payslip_account'})
        expense_paid_before_payslip_move_posting = self.create_expenses({'payment_mode': 'payslip_account'})
        expense_normal = self.create_expenses({'payment_mode': 'payslip_account'})
        expenses = expense_paid_before_payslip_creation | expense_paid_before_payslip_move_posting | expense_normal
        expenses.action_submit()
        expenses._do_approve()  # Skip duplicate wizard
        for expense in expenses:  # Ensure we get three distinct moves
            expense._post_without_wizard_payslip_mode()

        self.assertRecordValues(expenses, [
            {'total_amount': 1000.0, 'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted', 'refund_in_payslip': True, 'payslip_id': False},
        ])
        self.assertRecordValues(expenses.account_move_id, [
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid', 'state': 'posted'},
        ])

        self.get_new_payment(expense_paid_before_payslip_creation, 1000.0)
        self.assertRecordValues(expenses.sorted('state'), [
            # refund_in_payslip flag isn't reset, but we currently do not need it to be
            {'total_amount': 1000.0, 'state': paid_or_in_payment_state, 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted',                 'refund_in_payslip': True, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': 'posted',                 'refund_in_payslip': True, 'payslip_id': False},
        ])
        self.assertRecordValues(expenses.account_move_id.sorted('payment_state'), [
            {'amount_total': 1000.0, 'amount_residual': 0.0,    'payment_state': paid_or_in_payment_state, 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid',               'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid',               'state': 'posted'},
        ])
        payslip = self.create_payslip()
        self.assertEqual(
            2000.0,
            payslip._get_input_line_amount('EXPENSES'),
            "The expense total amount of the two expenses in 'approved' state should be added to the new payslip expense input line",
        )
        payslip.compute_sheet()
        self.assertEqual(
            2000.0,
            payslip._get_line_values(['EXPENSES'])['EXPENSES'][payslip.id]['total'],
            "The expense total amount of the two expenses in 'approved' state should be added to the expense payslip line",
        )
        payslip.action_payslip_done()

        ctx = {'active_model': 'account.move', 'active_ids': expense_paid_before_payslip_move_posting.account_move_id.ids}
        payment_register = self.env['account.payment.register'].with_context(**ctx).create({
                'amount': expense_paid_before_payslip_move_posting.total_amount,
                'journal_id': self.company_data['default_journal_bank'].id,
                'payment_method_line_id': self.inbound_payment_method_line.id,
            })
        self.assertTrue(
            payment_register.is_already_paid_through_a_payslip,
            "We should have a warning that it's a bad idea to pay twice",
        )
        payment_register._create_payments()

        self.assertEqual(
            2000,
            payslip._get_input_line_amount('EXPENSES'),
            "The 2 linked expenses total amounts should be added to the new payslip expense input line",
        )
        self.assertRecordValues(expenses.sorted('state'), [
            {'total_amount': 1000.0, 'state': paid_or_in_payment_state, 'payslip_id': False},
            {'total_amount': 1000.0, 'state': paid_or_in_payment_state, 'payslip_id': payslip.id},
            {'total_amount': 1000.0, 'state': 'posted',                 'payslip_id': payslip.id},
        ])
        self.assertRecordValues(expenses.account_move_id.sorted('state'), [
            {'amount_total': 1000.0, 'amount_residual': 0.0,    'payment_state': paid_or_in_payment_state, 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 0.0,    'payment_state': paid_or_in_payment_state, 'state': 'posted'},
            {'amount_total': 1000.0, 'amount_residual': 1000.0, 'payment_state': 'not_paid',               'state': 'posted'},
        ])

        # Posting the move will result in `expense_paid_before_payslip_move_posting` being paid twice,
        # but as the warning has been ignored it's the user's problem. It should not raise
        payslip.move_id.action_post()

        # Check reconciliation
        # Get the corresponding account.partial.reconcile lines
        reconciliation_lines = self.get_reconciliation_lines_from_accounts([expense_normal._get_expense_account_destination()])

        misc_moves = reconciliation_lines.debit_move_id.move_id - (expenses.account_move_id | payslip.move_id)
        self.assertEqual(
            2,
            len(misc_moves),
            "There should be two moves, corresponding to the two payments done, as the payslip won't be automatically reconciled",
        )

        # 2 of the three lines of expense_lines_to_reconcile should be reconciled by the early payment, the last one should not
        expense_lines_to_reconcile, payslip_line_to_reconcile = self.get_all_amls_to_be_reconciled(expenses, payslip)

        self.assertFalse(
            payslip_line_to_reconcile.reconciled,
        "The payslip move should not be reconciled as one of the expense being already reconciled, there is a mismatch in the amounts",
        )
        expense_line_not_reconciled = expense_lines_to_reconcile.filtered(
            lambda line: line.matching_number == payslip_line_to_reconcile.matching_number
        )
        self.assertEqual(
            1,
            len(expense_line_not_reconciled),
            "One of the expense should be prepared for manual reconciliation with the payslip move, the one that wasn't paid before posting the payslip move"
        )
        expense_lines_reconciled = (expense_lines_to_reconcile - expense_line_not_reconciled).sorted('id')
        self.assertEqual(
            2,
            len(expense_lines_reconciled),
            "The two other expense lines should be properly reconciled"
        )
        pattern = re.compile(r'^\d+$')
        self.assertRegex(expense_lines_reconciled[0].matching_number, pattern, "The matching number should be a definitive one")
        self.assertRegex(expense_lines_reconciled[1].matching_number, pattern, "The matching number should be a definitive one")
        # Sorting by ID as there are two distinct reconciliation steps
        self.assertRecordValues(reconciliation_lines.sorted('id'), [
            {'amount': 1000.0, 'debit_move_id': misc_moves[0].line_ids.sorted('balance').ids[-1], 'credit_move_id': expense_lines_reconciled[0].id},
            {'amount': 1000.0, 'debit_move_id': misc_moves[1].line_ids.sorted('balance').ids[-1], 'credit_move_id': expense_lines_reconciled[1].id},
        ])

    @freeze_time('2024-01-01')
    def test_no_expense_rule_means_no_linkage(self):
        product_d = self.product_c.copy({
            'name': 'Product_d',
            'salary_rule_ids': [Command.set([])],
        })

        expense = self.create_expenses({'payment_mode': 'payslip_account', 'product_id': product_d.id, 'total_amount_currency': 1000.0})
        expense.action_submit()
        with self.assertRaises(UserError):
            expense.action_approve()

        self.assertRecordValues(expense, [
            {'state': 'submitted', 'refund_in_payslip': False, 'payslip_id': False},
        ])

    @freeze_time('2024-01-01')
    def test_unlink_payslip_moves_user(self):
        """ Test Account user are able to reset to draft payslip move and unlink them """
        user = self.env['res.users'].create({
            'name': 'Account user',
            'login': 'accountuser',
            'password': 'accountuser',
            'group_ids': [
                Command.link(self.env.ref('account.group_account_user').id),
            ],
        })

        expense = self.create_expenses({'payment_mode': 'payslip_account'})
        expense.action_submit()
        expense.action_approve()

        payslip = self.create_payslip()
        self.payslip_run.slip_ids.compute_sheet()
        self.payslip_run.action_validate()
        payslip.move_id.action_post()

        payslip.move_id.with_user(user).button_draft()
        payslip.move_id.with_user(user).unlink()

    @freeze_time('2025-01-01')
    def test_report_in_next_payslip_manager_rights(self):
        with self.with_user(self.expense_user_manager.login):
            expense = self.create_expenses({'payment_mode': 'payslip_account'})
            expense.action_submit()
            expense.action_approve()
