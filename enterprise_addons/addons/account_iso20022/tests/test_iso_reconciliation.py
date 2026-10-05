from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_iso20022.tests.test_sepa_credit_transfer import TestSEPACreditTransferCommon


@tagged('post_install', '-at_install')
class TestIsoReconciliation(TestSEPACreditTransferCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        branch = cls._create_company(
            name='Branch Company',
            parent_id=cls.company_data['company'].id,
        )
        cls.branch_data = cls.collect_company_accounting_data(branch)

        unrelated = cls._create_company(name='Unrelated Company')
        cls.unrelated_data = cls.collect_company_accounting_data(unrelated)

    def test_matching_on_transaction_uuid(self):
        """
        Assert that a payment and a bank statement line are matched if they have the same transaction_uuid.
        """
        bill = self.env['account.move'].create({
            'partner_id': self.partner_a.id,
            'move_type': 'in_invoice',
            'invoice_date': '2025-01-01',
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 100,
            })],
        })
        bill.action_post()
        bill_line = bill.line_ids.filtered(lambda l: l.account_id.account_type in {'asset_receivable', 'liability_payable'})

        # The payment_method_line_id should have a payment_account_id value to generate the correct journal entries.
        sepa_ct_method_line = self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct')
        sepa_ct_method_line.payment_account_id = self.outbound_payment_method_line.payment_account_id
        payment = self.env['account.payment.register'].with_context(
            active_ids=bill_line.move_id.ids,
            active_model='account.move',
        ).create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'payment_date': '2010-01-01',
            'payment_method_line_id': sepa_ct_method_line.id,
        })._create_payments()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
            },
        ])

        bank_statement_line._try_auto_reconcile_statement_lines()
        # Assert that the statement line has been reconciled with the payment and the invoice.
        self.assertEqual(
            payment.move_id.line_ids._all_reconciled_lines(),
            payment.move_id.line_ids | bank_statement_line.line_ids[1] | bill_line
        )
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

    def test_matching_transaction_uuid_no_payment_entry(self):
        # Check if accounting is installed as this test doesn't make sense without accounting installed
        self.ensure_installed('accountant')

        bill = self.env['account.move'].create({
            'partner_id': self.partner_a.id,
            'move_type': 'in_invoice',
            'invoice_date': '2025-01-01',
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 100,
            })],
        })
        bill.action_post()
        bill_line = bill.line_ids.filtered(lambda line: line.account_id.account_type in {'asset_receivable', 'liability_payable'})

        payment = self.env['account.payment.register'].with_context(
            active_ids=bill_line.move_id.ids,
            active_model='account.move',
        ).create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'payment_date': '2010-01-01',
            'payment_method_line_id': self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct').id,
        })._create_payments()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
            },
        ])

        bank_statement_line._try_auto_reconcile_statement_lines()

        self.assertEqual(
            payment.invoice_ids.line_ids.filtered(lambda line: line.account_type == 'liability_payable'),
            bank_statement_line.line_ids.reconciled_lines_ids,
        )
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

    def test_matching_transaction_uuid_single_payment(self):
        # Check if accounting is installed as this test doesn't make sense without accounting installed
        self.ensure_installed('accountant')

        payment = self.env['account.payment'].create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'date': '2010-01-01',
            'partner_id': self.partner_a.id,
            'payment_method_line_id': self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct').id,
            'payment_type': 'outbound',
        })
        payment.action_post()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
            },
        ])
        bank_statement_line._try_auto_reconcile_statement_lines()
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

        self.assertRecordValues(
            bank_statement_line.line_ids,
            [
                {
                    'balance': -100.0,
                    'account_id': bank_statement_line.journal_id.default_account_id.id,
                    'name': bank_statement_line.payment_ref,
                },
                {
                    'balance': 100.0,
                    'account_id': self.partner_a.property_account_payable_id.id,
                    'name': payment.name,
                }
            ]
        )

    def test_no_transaction_uuid_matching_across_unrelated_companies(self):
        """
        Assert that a bank statement line is NOT matched against a payment from an
        unrelated company via transaction_uuid, even when both share the same UUID
        (e.g. two companies on the same database doing an intercompany bank transfer).
        """
        bill = self.env['account.move'].create({
            'partner_id': self.partner_a.id,
            'move_type': 'in_invoice',
            'invoice_date': '2025-01-01',
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 100,
            })],
            'company_id': self.company_data['company'].id,
        })
        bill.action_post()

        sepa_ct_method_line = self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct')
        sepa_ct_method_line.payment_account_id = self.outbound_payment_method_line.payment_account_id
        payment = self.env['account.payment.register'].with_context(
            active_ids=bill.ids,
            active_model='account.move',
        ).create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'payment_date': '2010-01-01',
            'payment_method_line_id': sepa_ct_method_line.id,
            'company_id': self.company_data['company'].id,
        })._create_payments()

        bank_statement_line = self.env['account.bank.statement.line'].create({
            'journal_id': self.unrelated_data['default_journal_bank'].id,
            'date': '2020-01-01',
            'payment_ref': 'PAYMENT',
            'amount': -100,
            'transaction_uuid': payment.transaction_uuid,
            'company_id': self.unrelated_data['company'].id,
        })

        # sudo() replicates the SUPERUSER context used by the auto-reconciliation cron,
        # which has access to all companies and is what triggered the original bug.
        bank_statement_line.sudo()._try_auto_reconcile_statement_lines()

        self.assertFalse(bank_statement_line.is_reconciled)

    def test_matching_transaction_uuid_draft_payment(self):
        payment = self.env['account.payment'].create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'date': '2010-01-01',
            'partner_id': self.partner_a.id,
            'payment_method_line_id': self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct').id,
            'payment_type': 'outbound',
        })

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
            },
        ])
        bank_statement_line._try_auto_reconcile_statement_lines()

        # Keep draft payment as draft (even if the reconciliation is done)
        self.assertEqual(payment.state, 'draft')
        self.assertRecordValues(
            bank_statement_line.line_ids,
            [
                {
                    'balance': -100.0,
                    'account_id': bank_statement_line.journal_id.default_account_id.id,
                    'name': bank_statement_line.payment_ref,
                },
                {
                    'balance': 100.0,
                    'account_id': self.partner_a.property_account_payable_id.id,
                    'name': payment.name,
                }
            ]
        )

    def test_matching_transaction_uuid_only_access_to_branch_company_for_statement_line(self):
        bill = self.env['account.move'].create({
            'partner_id': self.partner_a.id,
            'move_type': 'in_invoice',
            'invoice_date': '2025-01-01',
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 100,
            })],
            'company_id': self.company_data['company'].id,
        })
        bill.action_post()

        # The payment_method_line_id should have a payment_account_id value to generate the correct journal entries.
        sepa_ct_method_line = self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct')
        sepa_ct_method_line.payment_account_id = self.outbound_payment_method_line.payment_account_id
        payment = self.env['account.payment.register'].with_context(
            active_ids=bill.ids,
            active_model='account.move',
        ).create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'payment_date': '2010-01-01',
            'payment_method_line_id': sepa_ct_method_line.id,
            'company_id': self.company_data['company'].id,
        })._create_payments()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
                'company_id': self.branch_data['company'].id,
            },
        ])

        # Make sure that user has only access to the branch company
        self.env.user.company_id = self.branch_data['company'].id
        self.env.user.company_ids = self.branch_data['company'].ids
        bank_statement_line.with_company(self.branch_data['company'])._try_auto_reconcile_statement_lines()
        # Reset allowed companies for the test
        self.env.user.company_ids = (self.branch_data['company'] | self.company_data['company']).ids
        self.assertEqual(
            bank_statement_line.line_ids.reconciled_lines_ids,
            payment.move_id.line_ids.filtered(lambda line: line.account_id == self.outbound_payment_method_line.payment_account_id),
        )
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

    def test_matching_transaction_uuid_access_to_main_and_branch_company_for_statement_line(self):
        bill = self.env['account.move'].create({
            'partner_id': self.partner_a.id,
            'move_type': 'in_invoice',
            'invoice_date': '2025-01-01',
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 100,
            })],
            'company_id': self.company_data['company'].id,
        })
        bill.action_post()

        # The payment_method_line_id should have a payment_account_id value to generate the correct journal entries.
        sepa_ct_method_line = self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct')
        sepa_ct_method_line.payment_account_id = self.outbound_payment_method_line.payment_account_id
        payment = self.env['account.payment.register'].with_context(
            active_ids=bill.ids,
            active_model='account.move',
        ).create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'payment_date': '2010-01-01',
            'payment_method_line_id': sepa_ct_method_line.id,
            'company_id': self.company_data['company'].id,
        })._create_payments()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
                'company_id': self.branch_data['company'].id,
            },
        ])

        bank_statement_line.with_company(self.branch_data['company'])._try_auto_reconcile_statement_lines()
        self.assertEqual(
            bank_statement_line.line_ids.reconciled_lines_ids,
            payment.move_id.line_ids.filtered(lambda line: line.account_id == self.outbound_payment_method_line.payment_account_id),
        )
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

    def test_matching_transaction_uuid_single_payment_only_access_to_branch_company_for_statement_line(self):
        # Check if accounting is installed as this test doesn't make sense without accounting installed
        self.ensure_installed('accountant')

        payment = self.env['account.payment'].create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'date': '2010-01-01',
            'partner_id': self.partner_a.id,
            'payment_method_line_id': self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct').id,
            'payment_type': 'outbound',
            'company_id': self.company_data['company'].id,
        })
        payment.action_post()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
                'company_id': self.branch_data['company'].id,
            },
        ])
        # Make sure that user has only access to the branch company
        self.env.user.company_id = self.branch_data['company'].id
        self.env.user.company_ids = self.branch_data['company'].ids
        bank_statement_line._try_auto_reconcile_statement_lines()
        # Reset allowed companies for the test
        self.env.user.company_ids = (self.branch_data['company'] | self.company_data['company']).ids
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

        self.assertRecordValues(
            bank_statement_line.line_ids,
            [
                {
                    'balance': -100.0,
                    'account_id': bank_statement_line.journal_id.default_account_id.id,
                    'name': bank_statement_line.payment_ref,
                },
                {
                    'balance': 100.0,
                    'account_id': self.partner_a.property_account_payable_id.id,
                    'name': payment.name,
                }
            ]
        )

    def test_matching_transaction_uuid_single_payment_access_to_main_and_branch_company_for_statement_line(self):
        # Check if accounting is installed as this test doesn't make sense without accounting installed
        self.ensure_installed('accountant')

        payment = self.env['account.payment'].create({
            'amount': 100,
            'journal_id': self.bank_journal.id,
            'date': '2010-01-01',
            'partner_id': self.partner_a.id,
            'payment_method_line_id': self.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct').id,
            'payment_type': 'outbound',
            'company_id': self.company_data['company'].id,
        })
        payment.action_post()

        bank_statement_line = self.env['account.bank.statement.line'].create([
            {
                'journal_id': self.bank_journal.id,
                'date': '2020-01-01',
                'payment_ref': 'PAYMENT',
                'amount': -100,
                'sequence': 1,
                'transaction_uuid': payment.transaction_uuid,
                'company_id': self.branch_data['company'].id,
            },
        ])
        bank_statement_line._try_auto_reconcile_statement_lines()
        # Assert that the payment has been automatically validated.
        self.assertEqual(payment.state, 'reconciled')

        self.assertRecordValues(
            bank_statement_line.line_ids,
            [
                {
                    'balance': -100.0,
                    'account_id': bank_statement_line.journal_id.default_account_id.id,
                    'name': bank_statement_line.payment_ref,
                },
                {
                    'balance': 100.0,
                    'account_id': self.partner_a.property_account_payable_id.id,
                    'name': payment.name,
                }
            ]
        )
