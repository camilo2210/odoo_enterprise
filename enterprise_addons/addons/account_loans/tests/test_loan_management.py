from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_loans import _account_loans_add_date_column


@tagged('post_install', '-at_install')
class TestLoanManagement(AccountTestInvoicingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loan_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'general'),
            ('id', '!=', cls.company.currency_exchange_journal_id.id),
        ], limit=1)
        cls.long_term_account = cls.env['account.account'].search([
            ('company_ids', '=', cls.company.id),
            ('account_type', '=', 'liability_non_current'),
        ], limit=1)
        cls.short_term_account = cls.env['account.account'].search([
            ('company_ids', '=', cls.company.id),
            ('account_type', '=', 'liability_current'),
        ], limit=1)
        cls.expense_account = cls.env['account.account'].search([
            ('company_ids', '=', cls.company.id),
            ('account_type', '=', 'expense'),
            ('id', '!=', cls.company.account_journal_early_pay_discount_loss_account_id.id),
        ], limit=1)
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Test Analytic Account',
            'company_id': cls.company.id,
            'plan_id': cls.env['account.analytic.plan'].create({'name': 'Test Analytic Plan'}).id,
        })

    def create_loan(self, name, date, duration, amount_borrowed, interest, validate=False, skip_until_date=False):
        loan = self.env['account.loan'].create({
            'name': name,
            'date': date,
            'duration': duration,
            'amount_borrowed': amount_borrowed,
            'interest': interest,
            'skip_until_date': skip_until_date,
            'journal_id': self.loan_journal.id,
            'long_term_account_id': self.long_term_account.id,
            'short_term_account_id': self.short_term_account.id,
            'expense_account_id': self.expense_account.id,
            'line_ids': [
                Command.create({
                    'date': fields.Date.to_date(date) + relativedelta(months=month),
                    'principal': amount_borrowed / duration,
                    'interest': interest / duration,
                }) for month in range(duration)
            ],
        })
        if validate:
            loan.action_confirm()
        return loan

    @freeze_time('2024-07-31')
    def test_loan_values(self):
        """Test that the loan values are correctly computed"""
        # Create the loan
        loan = self.create_loan('Odoomobile Loan 🚗', '2024-01-01', 2 * 12, 24_000, 2_400, validate=True)

        # Verify that the outstanding balance of the loan is correct
        self.assertEqual(loan.outstanding_balance, 17_000)  # = 24_000 - (1_000 of principal * 7 months (Jan -> July))

        # Verify that the loan lines are correct (computed fields)
        self.assertEqual(len(loan.line_ids), 24)  # 24 months
        self.assertRecordValues(loan.line_ids[0] | loan.line_ids[4] | loan.line_ids[-1], [{
            'date': fields.Date.to_date('2024-01-01'),
            'principal': 1_000,
            'interest': 100,
            'payment': 1_100,
            'outstanding_balance': 23_000,  # = 24_000 - 1_000 principal * 1 month
        }, {
            'date': fields.Date.to_date('2024-05-01'),
            'principal': 1_000,
            'interest': 100,
            'payment': 1_100,
            'outstanding_balance': 19_000,  # = 24_000 - 1_000 principal * 5 months
        }, {
            'date': fields.Date.to_date('2025-12-01'),
            'principal': 1_000,
            'interest': 100,
            'payment': 1_100,
            'outstanding_balance': 0,
        }])

        # Verify that the generated moves are correct
        payment_moves = loan.line_ids.generated_move_ids.filtered(lambda m: len(m.line_ids) == 3)  # payments moves have 3 lines (principal + interest = payment)
        self.assertEqual(len(payment_moves), 24)  # 24 months
        reclassification_moves = (loan.line_ids.generated_move_ids - payment_moves).filtered(lambda m: not m.reversed_entry_id)  # reclassification moves have 2 lines (moving principal from one account to another) and have no link to a reversed entry
        self.assertEqual(len(reclassification_moves), 23)  # one less because we have an offset of one month (the first month is already started and should not be reclassified)
        reclassification_reverse_moves = (loan.line_ids.generated_move_ids - payment_moves) - reclassification_moves
        self.assertEqual(len(reclassification_reverse_moves), 23)  # same

        # Verify that the payment_moves are correct
        self.assertRecordValues(payment_moves[0] | payment_moves[11] | payment_moves[15] | payment_moves[-1], [{
            'date': fields.Date.to_date('2024-01-01'),
            'ref': "Odoomobile Loan 🚗 - Principal & Interest 01/2024",
            'amount_total': 1_100,  # 1_000 principal + 100 interest
            'generating_loan_line_id': loan.line_ids[0].id,
        }, {
            'date': fields.Date.to_date('2024-12-01'),
            'ref': "Odoomobile Loan 🚗 - Principal & Interest 12/2024",
            'amount_total': 1_100,  # 1_000 principal + 100 interest
            'generating_loan_line_id': loan.line_ids[11].id,
        }, {
            'date': fields.Date.to_date('2025-04-01'),
            'ref': "Odoomobile Loan 🚗 - Principal & Interest 04/2025",
            'amount_total': 1_100,  # 1_000 principal + 100 interest
            'generating_loan_line_id': loan.line_ids[15].id,
        }, {
            'date': fields.Date.to_date('2025-12-01'),
            'ref': "Odoomobile Loan 🚗 - Principal & Interest 12/2025",
            'amount_total': 1_100,  # 1_000 principal + 100 interest
            'generating_loan_line_id': loan.line_ids[-1].id,
        }])

        self.assertRecordValues(payment_moves[0].line_ids.sorted(lambda l: -l.debit), [{
            'name': 'Odoomobile Loan 🚗 - Principal 01/2024',
            'debit': 1_000,
            'credit': 0,
            'account_id': self.long_term_account.id,
        }, {
            'name': 'Odoomobile Loan 🚗 - Interest 01/2024',
            'debit': 100,
            'credit': 0,
            'account_id': self.expense_account.id,
        }, {
            'name': 'Odoomobile Loan 🚗 - Due 01/2024 (Principal $ 1,000.00 + Interest $ 100.00)',
            'debit': 0,
            'credit': 1_100,
            'account_id': self.short_term_account.id,
        }])

        # Verify that the reclassification moves are correct
        self.assertRecordValues(reclassification_moves[0] | reclassification_moves[11] | reclassification_moves[15], [{
            'date': fields.Date.to_date('2024-01-01'),
            'ref': "Odoomobile Loan 🚗 - Reclassification LT - ST 02/2024 to 01/2025",  # offset of 1 month
            'amount_total': 12_000,  # sum of the principals of the next 12 months
            'generating_loan_line_id': loan.line_ids[0].id,
        }, {
            'date': fields.Date.to_date('2024-12-01'),
            'ref': "Odoomobile Loan 🚗 - Reclassification LT - ST 01/2025 to 12/2025",  # offset of 1 month
            'amount_total': 12_000,  # sum of the principals between 01/25 and 12/25
            'generating_loan_line_id': loan.line_ids[11].id,
        }, {
            'date': fields.Date.to_date('2025-04-01'),
            'ref': "Odoomobile Loan 🚗 - Reclassification LT - ST 05/2025 to 12/2025",  # offset of 1 month
            'amount_total': 8_000,  # sum of the principals between 05/25 and 12/25
            'generating_loan_line_id': loan.line_ids[15].id,
        }])

        self.assertRecordValues(reclassification_moves[0].line_ids.sorted(lambda l: l.credit), [{
            'name': f'Odoomobile Loan 🚗 - Reclassification LT - ST 02/2024 to 01/2025 (To {self.short_term_account.code})',
            'debit': 12_000,
            'credit': 0,
            'account_id': self.long_term_account.id,
        }, {
            'name': f'Odoomobile Loan 🚗 - Reclassification LT - ST 02/2024 to 01/2025 (From {self.long_term_account.code})',
            'debit': 0,
            'credit': 12_000,
            'account_id': self.short_term_account.id,
        }])

        # Verify that the reverse reclassification moves are correct
        self.assertRecordValues(reclassification_reverse_moves[0] | reclassification_reverse_moves[11] | reclassification_reverse_moves[15], [{
            'date': fields.Date.to_date('2024-02-01'),
            'ref': "Odoomobile Loan 🚗 - Reversal reclassification LT - ST 02/2024 to 01/2025",  # offset of 1 month
            'amount_total': 12_000,  # sum of the principals of the next 12 months
            'generating_loan_line_id': loan.line_ids[0].id,
        }, {
            'date': fields.Date.to_date('2025-01-01'),
            'ref': "Odoomobile Loan 🚗 - Reversal reclassification LT - ST 01/2025 to 12/2025",  # offset of 1 month
            'amount_total': 12_000,  # sum of the principals between 01/25 and 12/25
            'generating_loan_line_id': loan.line_ids[11].id,
        }, {
            'date': fields.Date.to_date('2025-05-01'),
            'ref': "Odoomobile Loan 🚗 - Reversal reclassification LT - ST 05/2025 to 12/2025",  # offset of 1 month
            'amount_total': 8_000,  # sum of the principals between 05/25 and 12/25
            'generating_loan_line_id': loan.line_ids[15].id,
        }])

        self.assertRecordValues(reclassification_reverse_moves[0].line_ids.sorted(lambda l: l.debit), [{
            'name': f'Odoomobile Loan 🚗 - Reversal reclassification LT - ST 02/2024 to 01/2025 (To {self.short_term_account.code})',
            'credit': 12_000,
            'debit': 0,
            'account_id': self.long_term_account.id,
        }, {
            'name': f'Odoomobile Loan 🚗 - Reversal reclassification LT - ST 02/2024 to 01/2025 (From {self.long_term_account.code})',
            'credit': 0,
            'debit': 12_000,
            'account_id': self.short_term_account.id,
        }])

    @freeze_time('2024-07-31')
    def test_loan_states(self):
        """Test the flow of the loan: Draft, Running, Closed, Cancelled"""
        # Create the loan
        loan = self.create_loan('Odoomobile Loan 🚗', '2024-01-01', 12, 24_000, 2_400)

        # Verify that the loan is in draft
        self.assertEqual(loan.state, 'draft')
        self.assertFalse(loan.line_ids.generated_move_ids)

        # Verify that the loan is running
        loan.action_confirm()
        self.assertEqual(loan.state, 'running')
        self.assertTrue(loan.line_ids.generated_move_ids)
        self.assertTrue(
            any(m.state == 'posted' for m in loan.line_ids.generated_move_ids)
            and
            any(m.state == 'draft' for m in loan.line_ids.generated_move_ids)
        )  # Mix of draft & posted entries

        # Verify that the loan is cancelled
        loan.action_cancel()
        self.assertEqual(loan.state, 'cancelled')
        self.assertFalse(loan.line_ids.generated_move_ids)

        # Verify that we can reset to draft the loan
        loan.action_set_to_draft()
        self.assertEqual(loan.state, 'draft')
        self.assertFalse(loan.line_ids.generated_move_ids)

        # Run it again
        loan.action_confirm()
        self.assertEqual(loan.state, 'running')
        self.assertTrue(loan.line_ids.generated_move_ids)

        # Close the loan, only draft entries should be removed
        action = loan.action_close()
        wizard = self.env[action['res_model']].browse(action['res_id'])
        wizard.date = fields.Date.to_date('2024-10-31')
        wizard.action_save()
        self.assertEqual(loan.state, 'closed')
        self.assertEqual(len(loan.line_ids.generated_move_ids), 30)  # = 24 payment moves + 23 reclassification moves + 23 reversed reclass - (14 + 13 + 13) cancelled moves

        # Reset to draft, the entries should be removed
        loan.action_set_to_draft()
        self.assertEqual(loan.state, 'draft')
        self.assertFalse(loan.line_ids.generated_move_ids)

        # Create a new loan that should be automatically closed when the last generated move is posted
        loan2 = self.create_loan('Odoomobile Loan 🚗', '2024-01-01', 12, 24_000, 2_400, validate=True)
        self.assertEqual(loan2.state, 'running')
        with freeze_time('2024-12-31'), self.enter_registry_test_mode():
            self.env.ref('account.ir_cron_auto_post_draft_entry').method_direct_trigger()
            self.assertEqual(loan2.state, 'closed')

    @freeze_time('2024-06-23')
    def test_loan_states_with_audit_trail(self):
        """Test the flow of the loan: Draft, Running, Closed, Cancelled"""
        self.company.restrictive_audit_trail = True
        # Create the loan
        loan = self.create_loan('Odoomobile Loan 🚗', '2024-01-01', 12, 24_000, 2_400)

        # Verify that the loan is in draft
        self.assertEqual(loan.state, 'draft')
        self.assertFalse(loan.line_ids.generated_move_ids)

        # Verify that the loan is running
        loan.action_confirm()
        self.assertEqual(loan.state, 'running')
        self.assertEqual(len(loan.line_ids.generated_move_ids.filtered(lambda m: m.state == 'posted')), 17)
        self.assertEqual(len(loan.line_ids.generated_move_ids), 34)

        # Verify that the loan is cancelled
        loan.action_cancel()
        self.assertEqual(loan.state, 'cancelled')
        self.assertFalse(len(loan.line_ids.generated_move_ids.filtered(lambda m: m.state == 'posted')))
        self.assertEqual(len(loan.line_ids.generated_move_ids), 17)

        # Verify that we can reset to draft the loan
        loan.action_set_to_draft()
        self.assertEqual(loan.state, 'draft')
        self.assertEqual(len(loan.line_ids.generated_move_ids), 17)

        # Run it again
        loan.action_confirm()
        self.assertEqual(loan.state, 'running')
        self.assertEqual(len(loan.line_ids.generated_move_ids.filtered(lambda m: m.state == 'posted')), 17)
        self.assertEqual(len(loan.line_ids.generated_move_ids), 51)

        # Close the loan, only draft entries should be removed
        action = loan.action_close()
        wizard = self.env[action['res_model']].browse(action['res_id'])
        wizard.action_save()
        self.assertEqual(loan.state, 'closed')
        self.assertEqual(len(loan.line_ids.generated_move_ids.filtered(lambda m: m.state == 'posted')), 17)
        self.assertEqual(len(loan.line_ids.generated_move_ids), 35)

        # Reset to draft, the entries should be removed
        loan.action_set_to_draft()
        self.assertEqual(loan.state, 'draft')
        self.assertFalse(len(loan.line_ids.generated_move_ids.filtered(lambda m: m.state == 'posted')))
        self.assertEqual(len(loan.line_ids.generated_move_ids), 34)

    @freeze_time('2024-01-01')
    def test_loan_import_amortization_schedule(self):
        """Test that we can import an amortization schedule from a file"""
        # Upload the file from the List View -> Create a new Loan
        with file_open('account_loans/demo/files/loan_amortization_demo.csv', 'rb') as f:
            attachment = self.env['ir.attachment'].create({
                'name': 'loan_amortization_demo.csv',
                'raw': f.read(),
            })
            attachment = _account_loans_add_date_column(attachment)  # fill the date column from -1 year to +3 years

        action = self.env['account.loan'].action_upload_amortization_schedule(attachment.id)
        loan = self.env['account.loan'].browse(action.get('params', {}).get('context', {}).get('default_loan_id'))
        import_wizard = self.env['base_import.import'].browse(action.get('params', {}).get('context', {}).get('wizard_id'))
        result = import_wizard.parse_preview({
            'quoting': '"',
            'separator': ',',
            'date_format': '%Y-%m-%d',
            'has_headers': True,
        })
        import_wizard.with_context(default_loan_id=loan.id).execute_import(
            ['date', 'principal', 'interest'],
            [],
            result["options"],
        )
        loan.action_file_uploaded()
        loan.write({
            'journal_id': self.loan_journal.id,
            'long_term_account_id': self.long_term_account.id,
            'short_term_account_id': self.short_term_account.id,
            'expense_account_id': self.expense_account.id,
        })
        loan.action_confirm()

        self.assertRecordValues(loan, [{
            'date': fields.Date.from_string('2023-01-01'),
            'state': 'running',
            'name': attachment.name,
            'amount_borrowed': 19_900.25,  # Sum of principals
            'outstanding_balance': 15_627.82,  # = 19_900.25 - principal of first 12 lines
        }])

        self.assertEqual(len(loan.line_ids), 48)  # 4 years
        self.assertRecordValues(loan.line_ids[0] | loan.line_ids[-1], [{
            'date': fields.Date.from_string('2023-01-01'),
            'principal': 304.60,
            'interest': 250.00,
            'payment': 554.6,
            'outstanding_balance': 19_595.65,  # = 19_900.25 - 304.60
        }, {
            'date': fields.Date.from_string('2026-12-01'),
            'principal': 547.72,
            'interest': 6.88,
            'payment': 554.6,
            'outstanding_balance': 0,
        }])

        # Upload the file from the Form View -> Update the current Loan
        loan2 = self.create_loan('Loan 2', '2024-01-01', 2 * 12, 24_000, 2_400, validate=True)
        self.assertEqual(len(loan2.line_ids), 24)

        # Override all previous lines, and recompute amount_borrowed, date, ...
        action = loan2.action_upload_amortization_schedule(attachment.id)
        self.assertEqual(action.get('params', {}).get('context', {}).get('default_loan_id'), loan2.id)
        import_wizard = self.env['base_import.import'].browse(action.get('params', {}).get('context', {}).get('wizard_id'))
        result = import_wizard.parse_preview({
            'quoting': '"',
            'separator': ',',
            'date_format': '%Y-%m-%d',
            'has_headers': True,
        })
        import_wizard.with_context(default_loan_id=loan2.id).execute_import(
            ['date', 'principal', 'interest'],
            [],
            result["options"],
        )
        loan2.action_file_uploaded()
        loan2.action_confirm()

        self.assertRecordValues(loan, [{
            'date': fields.Date.from_string('2023-01-01'),
            'state': 'running',
            'name': attachment.name,
            'amount_borrowed': 19_900.25,  # Sum of principals
            'outstanding_balance': 15_627.82,  # = 19_900.25 - principal of first 12 lines
        }])

        self.assertEqual(len(loan.line_ids), 48)  # 4 years
        self.assertRecordValues(loan.line_ids[0] | loan.line_ids[-1], [{
            'date': fields.Date.from_string('2023-01-01'),
            'principal': 304.60,
            'interest': 250.00,
            'payment': 554.6,
            'outstanding_balance': 19_595.65,  # = 19_900.25 - 304.60
        }, {
            'date': fields.Date.from_string('2026-12-01'),
            'principal': 547.72,
            'interest': 6.88,
            'payment': 554.6,
            'outstanding_balance': 0,
        }])

    def test_loan_zero_interest(self):
        loan = self.env['account.loan'].create({'name': '0 interest loan', 'date': '2024-01-01', 'amount_borrowed': 24_000})
        wizard = self.env['account.loan.compute.wizard'].browse(loan.action_open_compute_wizard()['res_id'])
        wizard.interest_rate = 0
        wizard.action_save()
        self.assertEqual(len(loan.line_ids), 12)  # default loan term is 1 year = 12 months
        self.assertTrue(all(payment == 2000 for payment in loan.line_ids.mapped('payment')))  # 24,000 / 12 months = 2,000/month

    @freeze_time('2024-07-31')
    def test_loan_skip_until_date(self):
        """Test the skip_until_date field"""
        loan = self.create_loan('Odoomobile Loan 🚗', '2024-01-01', 12, 24_000, 2_400, validate=True, skip_until_date='2024-05-15')

        self.assertEqual(loan.state, 'running')
        self.assertTrue(loan.line_ids.generated_move_ids)
        # Outstanding balance should be 24_000 - 2_000 * 7 months (Jan -> July), including skipped period
        self.assertEqual(loan.outstanding_balance, 10_000)

    @freeze_time('2025-01-01')
    def test_loan_skip_until_date_2(self):
        """Test loan closing when skip_until_date field is set"""
        loan = self.env['account.loan'].create({
            'name': 'Test',
            'date': '2024-01-01',
            'duration': 12,
            'amount_borrowed': 20_000,
            'interest': 107.87,
            'skip_until_date': '2024-10-31',
            'journal_id': self.loan_journal.id,
            'long_term_account_id': self.long_term_account.id,
            'short_term_account_id': self.short_term_account.id,
            'expense_account_id': self.expense_account.id,
        })

        wizard = self.env['account.loan.compute.wizard'].browse(loan.action_open_compute_wizard()['res_id'])
        wizard.action_save()
        loan.action_confirm()

        self.assertTrue(loan.line_ids.generated_move_ids)
        self.assertEqual(loan.state, 'closed')

    def test_loan_analytic_distribution_propagation(self):
        """Test that the analytic distribution on a loan propagates to all generated moves."""
        test_distribution = {str(self.analytic_account.id): 100.0}
        loan = self.create_loan('Analytic Test Loan', '2024-01-01', 12, 12_000, 1_200, validate=False)
        loan.write({'analytic_distribution': test_distribution})

        self.assertEqual(loan.analytic_distribution, test_distribution)

        loan.action_confirm()
        payment_moves = loan.line_ids.generated_move_ids.filtered(lambda m: m.is_loan_payment_move)
        self.assertTrue(payment_moves, "Payment moves were not generated")

        for move in payment_moves:
            for line in move.line_ids:
                self.assertEqual(
                    line.analytic_distribution,
                    test_distribution,
                    f"Analytic distribution failed to propagate to payment move line: {line.name}"
                )

        reclass_moves = loan.line_ids.generated_move_ids - payment_moves
        self.assertTrue(reclass_moves, "Reclassification moves were not generated")

        for move in reclass_moves:
            for line in move.line_ids:
                self.assertEqual(
                    line.analytic_distribution,
                    test_distribution,
                    f"Analytic distribution failed to propagate to reclassification move line: {line.name}"
                )

    def test_loan_analytic_distribution_empty(self):
        """Test that confirming a loan without analytics does not crash or inject false data."""
        loan = self.create_loan('Empty Analytic Loan', '2024-01-01', 12, 12_000, 1_200, validate=True)
        self.assertFalse(loan.analytic_distribution)

        all_move_lines = loan.line_ids.generated_move_ids.mapped('line_ids')
        for line in all_move_lines:
            self.assertFalse(
                line.analytic_distribution,
                f"Analytic distribution should be empty on move line: {line.name}"
            )

    @freeze_time('2026-07-01')
    def test_loan_analytic_profitability_evolution(self):
        """
        Test the evolution of analytic profitability (interest loss) over time.
        Verifies that as loan payment moves are posted, only the interest expense
        trickles down into the analytic ledger as a loss, ensuring accurate
        month-by-month P&L reporting
        """
        test_distribution = {str(self.analytic_account.id): 100.0}

        loan = self.create_loan('Analytic Evolution Loan', '2025-02-01', 12, 12_000, 1_200, validate=False)
        loan.write({'analytic_distribution': test_distribution})
        loan.action_confirm()

        for line in loan.line_ids:
            move = line.generated_move_ids.filtered(lambda m: m.is_loan_payment_move)
            self.assertEqual(move.state, 'posted', f"Move for {line.date} did not auto-post.")

        read_group_result = self.env['account.analytic.line'].formatted_read_group(
            domain=[
                (self.analytic_account.plan_id._column_name(), '=', self.analytic_account.id),
                ('general_account_id.internal_group', 'in', ['income', 'expense']),
            ],
            groupby=[self.analytic_account.plan_id._column_name(), 'date:month'],
            aggregates=['amount:sum'],
        )

        for rg_cell, expected in zip(read_group_result, [
            ('2025-02-01', -100.0),
            ('2025-03-01', -100.0),
            ('2025-04-01', -100.0),
            ('2025-05-01', -100.0),
            ('2025-06-01', -100.0),
            ('2025-07-01', -100.0),
            ('2025-08-01', -100.0),
            ('2025-09-01', -100.0),
            ('2025-10-01', -100.0),
            ('2025-11-01', -100.0),
            ('2025-12-01', -100.0),
            ('2026-01-01', -100.0),
        ]):
            self.assertEqual((rg_cell['date:month'][0], rg_cell['amount:sum']), expected)

    def test_normal_accounting_date_calculation(self):
        """ Test that a payment in the following month snaps to the 1st """
        loan = self.env['account.loan'].create({
            'name': 'Test Normal Date',
            'date': '2026-06-15',
            'amount_borrowed': 10000,
            'journal_id': self.loan_journal.id,
            'expense_account_id': self.expense_account.id,
            'short_term_account_id': self.short_term_account.id,
            'long_term_account_id': self.long_term_account.id,
        })

        wizard = self.env['account.loan.compute.wizard'].with_context(active_id=loan.id).create({
            'loan_id': loan.id,
            'loan_amount': loan.amount_borrowed,
            'start_date': loan.date,
            'first_payment_date': fields.Date.to_date('2026-07-30'),  # NEXT month
            'payment_end_of_month': 'at_anniversary',
            'loan_term': 1,
            'interest_rate': 5.0,
        })
        wizard.action_save()

        first_line = loan.line_ids[0]
        self.assertEqual(first_line.date, fields.Date.to_date('2026-07-30'))

    def test_edge_case_same_month_accounting_date(self):
        """ Test that a payment in the same month does not predate the loan start date """
        loan = self.env['account.loan'].create({
            'name': 'Test Same Month',
            'date': '2026-06-15',
            'amount_borrowed': 10000,
            'journal_id': self.loan_journal.id,
            'expense_account_id': self.expense_account.id,
            'short_term_account_id': self.short_term_account.id,
            'long_term_account_id': self.long_term_account.id,
        })

        wizard = self.env['account.loan.compute.wizard'].with_context(active_id=loan.id).create({
            'loan_id': loan.id,
            'loan_amount': loan.amount_borrowed,
            'start_date': loan.date,
            'first_payment_date': fields.Date.to_date('2026-06-30'),  # SAME month
            'payment_end_of_month': 'at_anniversary',
            'loan_term': 1,
            'interest_rate': 5.0,
        })
        wizard.action_save()

        first_line = loan.line_ids[0]
        self.assertEqual(first_line.date, fields.Date.to_date('2026-06-30'))

    def test_journal_entry_move_dates(self):
        """ Test that action_confirm applies the correct dates to generated moves """
        loan = self.env['account.loan'].create({
            'name': 'Test Move Dates',
            'date': '2026-06-15',
            'amount_borrowed': 10000,
            'duration': 2,
            'interest': 500,
            'journal_id': self.loan_journal.id,
            'expense_account_id': self.expense_account.id,
            'short_term_account_id': self.short_term_account.id,
            'long_term_account_id': self.long_term_account.id,
        })

        wizard = self.env['account.loan.compute.wizard'].with_context(active_id=loan.id).create({
            'loan_id': loan.id,
            'loan_amount': loan.amount_borrowed,
            'start_date': loan.date,
            'first_payment_date': fields.Date.to_date('2026-07-17'),
            'payment_end_of_month': 'at_anniversary',
            'loan_term': 2,
            'interest_rate': 5.0,
        })
        wizard.action_save()
        loan.amount_borrowed = sum(loan.line_ids.mapped('principal'))
        loan.action_confirm()

        first_line = loan.line_ids.sorted('date')[0]
        moves = first_line.generated_move_ids

        payment_move = moves.filtered(lambda m: m.is_loan_payment_move)
        reclass_move = moves.filtered(lambda m: not m.is_loan_payment_move and not m.reversed_entry_id)
        reversal_move = moves.filtered(lambda m: m.reversed_entry_id)

        self.assertEqual(payment_move.date, fields.Date.to_date('2026-07-01'))
        self.assertEqual(reclass_move.date, fields.Date.to_date('2026-07-01'))
        # Reversal must be exactly one month later
        self.assertEqual(reversal_move.date, fields.Date.to_date('2026-08-01'))
