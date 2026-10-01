from contextlib import contextmanager

from odoo import Command
from odoo.tests import Form, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestJournalItemSplit(AccountTestInvoicingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bill = cls._create_invoice(
            move_type='in_invoice',
            invoice_line_ids=[
                cls._prepare_invoice_line(product_id=cls.product_a, quantity=5, price_unit=800.0),
                cls._prepare_invoice_line(product_id=cls.product_b, price_unit=160.0),
            ],
        )

    @contextmanager
    def _split_lines(self, lines):
        wizard_form = Form(self.env['account.split.journal.item.wizard'].with_context(
            default_line_ids=[Command.set(lines.ids)],
        ))
        try:
            yield wizard_form
        finally:
            wizard = wizard_form.save()
            total_before = self.bill.amount_total
            wizard.split()
            self.assertEqual(total_before, self.bill.amount_total)

    def test_split_by_line_quantity(self):
        line = self.bill.invoice_line_ids[0]

        with self._split_lines(line) as wizard:
            self.assertTrue(wizard.show_simple_wizard, f"Should only show simple wizard for line quantities != 2. line quantity: {line.quantity}")
            self.assertEqual(wizard.quantity, 5, "Wizard quantity should equal the line quantity.")

        self.assertInvoiceValues(
            self.bill,
            [
                *(5 * [{'product_id': self.product_a.id, 'balance': 800.0}]),
                {'product_id': self.product_b.id,   'balance': 160.0},
                {'product_id': False,               'balance': 624.0},
                {'product_id': False,               'balance': 24.0},
                {'product_id': False,               'balance': -4808.0},
            ],
            {},
        )

    def test_split_by_quanity(self):
        line = self.bill.invoice_line_ids[0]

        with self._split_lines(line) as wizard:
            wizard.quantity = 4
            self.assertTrue(wizard.show_simple_wizard)

        self.assertRecordValues(
            self.bill.invoice_line_ids,
            [
                {'product_id': self.product_a.id, 'balance': 1000.0,    'quantity': 1.25},
                {'product_id': self.product_b.id, 'balance': 160.0,     'quantity': 1.0},
                {'product_id': self.product_a.id, 'balance': 1000.0,    'quantity': 1.25},
                {'product_id': self.product_a.id, 'balance': 1000.0,    'quantity': 1.25},
                {'product_id': self.product_a.id, 'balance': 1000.0,    'quantity': 1.25},
            ],
        )

    def test_split_by_amount(self):
        line = self.bill.invoice_line_ids[1]

        with self._split_lines(line) as wizard:
            wizard.quantity = 2

            self.assertEqual(wizard.amount, line.balance / 2)

            wizard.amount = 100.0

        self.assertRecordValues(
            self.bill.invoice_line_ids,
            [
                {'product_id': self.product_a.id,   'balance': 4000.0,  'quantity': 5.0},
                {'product_id': self.product_b.id,   'balance': 60.0,    'quantity': 1.0},
                {'product_id': self.product_b.id,   'balance': 100.0,   'quantity': 1.0},
            ],
        )

    def test_split_by_account(self):
        line = self.bill.invoice_line_ids[0]
        accounts = [line.account_id.id for line in self.bill.invoice_line_ids]
        new_expense_account = self.bill.line_ids[0].account_id.copy({'name': "Expense 2"})

        with self._split_lines(line) as wizard:
            wizard.quantity = 2

            self.assertFalse(wizard.show_simple_wizard)

            wizard.account_id = new_expense_account
            self.assertNotEqual(line.account_id, wizard.account_id)

        self.assertRecordValues(
            self.bill.invoice_line_ids,
            [
                {'product_id': self.product_a.id,   'balance': 2000.0,  'account_id': accounts[0]},
                {'product_id': self.product_b.id,   'balance': 160.0,   'account_id': accounts[1]},
                {'product_id': self.product_a.id,   'balance': 2000.0,  'account_id': new_expense_account.id},
            ],
        )

    def test_split_multiple_lines(self):
        with self._split_lines(self.bill.invoice_line_ids) as wizard:
            self.assertTrue(wizard.show_simple_wizard)
            self.assertEqual(wizard.quantity, 2)

            wizard.quantity = 4

        self.assertRecordValues(
            self.bill.invoice_line_ids,
            [
                {'product_id': self.product_a.id,   'balance': 1000.0},
                {'product_id': self.product_b.id,   'balance': 40.0},
                {'product_id': self.product_a.id,   'balance': 1000.0},
                {'product_id': self.product_a.id,   'balance': 1000.0},
                {'product_id': self.product_a.id,   'balance': 1000.0},
                {'product_id': self.product_b.id,   'balance': 40.0},
                {'product_id': self.product_b.id,   'balance': 40.0},
                {'product_id': self.product_b.id,   'balance': 40.0},
            ],
        )

    def test_split_complex(self):
        line = self.bill.invoice_line_ids[0]
        accounts = [line.account_id.id for line in self.bill.invoice_line_ids]
        new_expense_account = self.bill.line_ids[0].account_id.copy({'name': "Expense 2"})

        with self._split_lines(line) as wizard:
            wizard.quantity = 2

            self.assertFalse(wizard.show_simple_wizard)

            wizard.amount = 3000
            wizard.account_id = new_expense_account

        self.assertRecordValues(
            self.bill.invoice_line_ids,
            [
                {'product_id': self.product_a.id,   'balance': 1000.0,  'account_id': accounts[0]},
                {'product_id': self.product_b.id,   'balance': 160.0,   'account_id': accounts[1]},
                {'product_id': self.product_a.id,   'balance': 3000.0,  'account_id': new_expense_account.id},
            ],
        )

    def test_split_without_product(self):
        expense_account_id = self.company_data['default_account_expense'].id
        revenue_account_id = self.company_data['default_account_revenue'].id
        entry = self._create_invoice(
            move_type='entry',
            invoice_line_ids=[
                Command.create({'debit': 100.0, 'account_id': expense_account_id}),
                Command.create({'credit': 100.0, 'account_id': revenue_account_id}),
            ],
        )

        line = entry.line_ids.filtered(lambda l: l.debit)

        with self._split_lines(line) as wizard:
            self.assertEqual(wizard.quantity, 2)
            self.assertFalse(wizard.show_simple_wizard)

        self.assertRecordValues(
            entry.line_ids,
            [
                {'balance': 50.0,   'account_id': expense_account_id},
                {'balance': -100.0, 'account_id': revenue_account_id},
                {'balance': 50.0,   'account_id': expense_account_id},
            ],
        )

    def test_split_with_discount(self):
        invoice = self._create_invoice_one_line(
            product_id=self.product_a,
            quantity=3.0,
            tax_ids=self.tax_sale_a,
            discount=20.0,
        )
        line = invoice.invoice_line_ids[0]

        with self._split_lines(line) as wizard:
            self.assertEqual(wizard.quantity, 3)
            self.assertTrue(wizard.show_simple_wizard)

        self.assertRecordValues(
            invoice.invoice_line_ids,
            [
                {'product_id': self.product_a.id,   'balance': -800.0},
                {'product_id': self.product_a.id,   'balance': -800.0},
                {'product_id': self.product_a.id,   'balance': -800.0},
            ],
        )

    def test_split_rounding_tax_included(self):
        tax_included = self.env['account.tax'].create({
            'name': 'Tax 20% Included',
            'amount_type': 'percent',
            'amount': 20.0,
            'price_include': True,
        })

        invoice = self._create_invoice_one_line(
            product_id=self.product_a,
            quantity=1.0,
            price_unit=10.0,
            tax_ids=tax_included,
        )
        line = invoice.invoice_line_ids[0]

        with self._split_lines(line) as wizard:
            wizard.quantity = 3
            self.assertTrue(wizard.show_simple_wizard)

        self.assertRecordValues(
            invoice.line_ids,
            [
                {'product_id': self.product_a.id, 'balance': -3.3},
                {'product_id': False, 'balance': -2.0},
                {'product_id': False, 'balance': 12.0},
                {'product_id': self.product_a.id, 'balance': -3.4},
                {'product_id': self.product_a.id, 'balance': -3.3},
            ],
        )
