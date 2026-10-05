from odoo import fields
from odoo.exceptions import RedirectWarning, ValidationError
from odoo.tests import tagged, freeze_time

from odoo.addons.l10n_ca_payment_cpa005.tests.common import CPA005Common


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time('2020-11-30 19:45:00')
class TestCPA005PAD(CPA005Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quick_ref('base.USD').active = True
        start_date = fields.Date.subtract(fields.Date.today(), years=1)
        cls.mandate_a = cls._create_cpa005_mandate(name='PAD-A', start_date=start_date)
        cls.mandate_b = cls._create_cpa005_mandate(
            name='PAD-B',
            start_date=start_date,
            partner_id=cls.partner_b,
            partner_bank_id=cls.bank_partner_b,
        )

    def test_cpa005_pad_record_d_file(self):
        """The inbound batch produces Record D lines and debit control totals."""
        payments = (
            self._create_cpa005_payment(partner_id=self.partner_a, partner_bank_id=self.bank_partner_a, amount=123.45)
            | self._create_cpa005_payment(partner_id=self.partner_b, partner_bank_id=self.bank_partner_b, amount=456.78)
        )
        batch = self._create_batch_payment(payments)

        generated = batch._generate_cpa005_file()
        lines = generated.splitlines()

        self.assertEqual(len(lines), len(payments) + 2, 'Header + one D record per payment + footer.')
        for line in lines:
            self.assertEqual(len(line), 1464, 'Every CPA 005 line must be 1464 characters.')

        self.assertEqual(lines[0][0], 'A', 'First record is the file header.')
        for line in lines[1:-1]:
            self.assertEqual(line[0], 'D', 'Inbound transactions must be Record D.')

        footer = lines[-1]
        self.assertEqual(footer[0], 'Z', 'Last record is the footer.')
        total_cents = sum(round(p.amount * 100) for p in payments)
        self.assertEqual(int(footer[24:38]), total_cents, 'Debit total value must hold the collected amount.')
        self.assertEqual(int(footer[38:46]), len(payments), 'Debit total count must hold the number of debits.')
        self.assertEqual(int(footer[46:60]), 0, 'Credit total value must be zero for an inbound file.')
        self.assertEqual(int(footer[60:68]), 0, 'Credit total count must be zero for an inbound file.')

    def test_cpa005_pad(self):
        self.maxDiff = None  # show full diff in case of errors
        self.journal.l10n_ca_cpa005_pad_fcn_number_next = 103
        self.company.sudo().write({"name": "Long Compàny Nàme"})
        transaction_codes = self.env["l10n_ca_cpa005.transaction.code"]
        code_370 = transaction_codes.search([("code", "=", "370")], limit=1)
        code_700 = transaction_codes.search([("code", "=", "700")], limit=1)
        payments = (
            self._create_cpa005_payment(
                l10n_ca_cpa005_transaction_code_id=code_370,
                partner_id=self.partner_a,
                amount=123.45,
                memo="partner_a_1",
            )
            | self._create_cpa005_payment(
                l10n_ca_cpa005_transaction_code_id=code_370,
                partner_id=self.partner_a,
                amount=543.21,
                memo="partner_a_2",
            )
            | self._create_cpa005_payment(
                l10n_ca_cpa005_transaction_code_id=code_370,
                partner_id=self.partner_b,
                amount=456.78,
                memo="partner_b_1", date=fields.Date.add(fields.Date.today(), days=1),
            )
            | self._create_cpa005_payment(
                l10n_ca_cpa005_transaction_code_id=code_700,
                partner_id=self.partner_b,
                amount=567.89,
                memo="partner_b_2",
            )
        )
        batch = self._create_batch_payment(payments)
        expected_item_trace_numbers = [f"{payment.id:022d}" for payment in payments.sorted()]
        expected = [
            # A record ("header")
            'A0000000011234567890010302033501600                    CAD                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              ',
            # D records ("incoming collections")
            f"D000000002123456789001033700000045678020336077788888444444444   {expected_item_trace_numbers[0]}000COMP_NAME      partner_b                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            f"D000000003123456789001037000000056789020335077788888444444444   {expected_item_trace_numbers[1]}000COMP_NAME      partner_b                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            f"D000000004123456789001033700000054321020335055566666333333333   {expected_item_trace_numbers[2]}000COMP_NAME      partner_a                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            f"D000000005123456789001033700000012345020335055566666333333333   {expected_item_trace_numbers[3]}000COMP_NAME      partner_a                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            # Z record ("footer")
            'Z000000006123456789001030000000016913300000004000000000000000000000000000000000000000000000000000000000000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        ',
        ]

        for line in expected:
            self.assertEqual(
                len(line), 1464, "Every line in our CPA file should have 1464 characters (excluding \\r\\n)."
            )

        self.assertEqual(
            len(expected),
            len(payments) + 2,
            "There should be an A record, one D record per payment and one Z record.",
        )

        generated = batch._generate_cpa005_file()
        self.assertEqual(
            generated.count("\r\n"), len(expected) - 1, "The generated CPA 005 file should use DOS line endings."
        )
        self.assertEqual(
            generated.count("à"), 0, "The generated CPA 005 file should not have special characters."
        )

        generated = generated.splitlines()
        self.assertEqual(len(generated), len(expected), "The generated CPA 005 file has an incorrect amount of lines.")

        for line in generated:
            self.assertEqual(
                len(line), 1464, "Every line in the generated CPA file should have 1464 characters (excluding \\r\\n)."
            )

        for generated_line, expected_line in zip(generated, expected):
            self.assertEqual(generated_line, expected_line, "Generated line in CPA 005 file does not match expected.")

    def test_cpa005_pad_fcn_sequence_independent(self):
        """The inbound (PAD) FCN sequence is separate from the outbound one."""
        self.journal.l10n_ca_cpa005_fcn_number_next = 50
        self.journal.l10n_ca_cpa005_pad_fcn_number_next = 200
        self.assertEqual(self.journal._l10n_ca_cpa005_next_file_creation_nr('inbound'), '0200')
        self.assertEqual(self.journal._l10n_ca_cpa005_next_file_creation_nr('outbound'), '0050')
        # The two sequences advance independently.
        self.assertEqual(self.journal._l10n_ca_cpa005_next_file_creation_nr('inbound'), '0201')
        self.assertEqual(self.journal._l10n_ca_cpa005_next_file_creation_nr('outbound'), '0051')

    def test_cpa005_pad_currency_mix_rejected(self):
        """An inbound file can't mix currencies."""
        usd_bank = self._create_ca_bank(
            partner_id=self.partner_b,
            account_number='555555555',
            l10n_ca_financial_institution_number='077788888',
        )
        usd_payment = self._create_cpa005_payment(
            partner_id=self.partner_b,
            partner_bank_id=usd_bank,
            currency_id=self.quick_ref('base.USD'),
            amount=10,
        )
        cad_payment = self._create_cpa005_payment(partner_id=self.partner_a, partner_bank_id=self.bank_partner_a, amount=123.45)
        batch = self._create_batch_payment(cad_payment | usd_payment)
        with self.assertRaisesRegex(ValidationError, "A Canadian EFT file can not contain multiple currencies"):
            batch._generate_cpa005_file()

    def test_cpa005_pad_missing_payor_bank_info(self):
        """Inbound validation flags payors whose bank account lacks the FI number."""
        bank_no_fi = self._create_ca_bank(partner_id=self.partner_a, account_number='888888888')
        payment = self._create_cpa005_payment(partner_id=self.partner_a, partner_bank_id=bank_no_fi, amount=10)
        batch = self._create_batch_payment(payment)
        with self.assertRaisesRegex(RedirectWarning, "financial institution of both the payor and the payee must be set"):
            batch.validate_batch()

    def test_cpa005_pad_due_date_too_far_in_future(self):
        """A PAD due date more than 2 business days after the file date is rejected (Standard 005)."""
        payment = self._create_cpa005_payment(
            partner_id=self.partner_a,
            partner_bank_id=self.bank_partner_a,
            amount=100,
            date='2020-12-10'
        )
        batch = self._create_batch_payment(payment)
        with self.assertRaisesRegex(RedirectWarning, r"Some due \(collection\) dates are outside the window allowed by CPA 005"):
            batch.validate_batch()

    def test_cpa005_pad_due_date_too_far_in_past(self):
        """A PAD due date more than 173 days before the file date is rejected (Standard 005)."""
        payment = self._create_cpa005_payment(
            partner_id=self.partner_a,
            partner_bank_id=self.bank_partner_a,
            amount=100,
            date=fields.Date.subtract(fields.Date.today(), days=200),
        )
        batch = self._create_batch_payment(payment)
        with self.assertRaisesRegex(RedirectWarning, r"Some due \(collection\) dates are outside the window allowed by CPA 005"):
            batch.validate_batch()

    def test_cpa005_account_number_too_long_rejected(self):
        """An account number longer than the 12-char CPA 005 field is rejected, not truncated."""
        long_bank = self._create_ca_bank(
            partner_id=self.partner_a,
            account_number='1234567890123',  # 13 characters
            l10n_ca_financial_institution_number='055566666',
        )
        self.mandate_a.partner_bank_id = long_bank
        payment = self._create_cpa005_payment(partner_id=self.partner_a, partner_bank_id=long_bank, amount=100)
        batch = self._create_batch_payment(payment)
        with self.assertRaisesRegex(RedirectWarning, "Bank account of both the payor and the payee must be set"):
            batch.validate_batch()

    def test_cpa005_payment_register_wizard_transaction_code(self):
        """The payment register wizard transfers the selected transaction code to the created payment."""
        invoice = self._create_invoice_one_line(price_unit=150.0, name='test line', post=True)
        payment = self._register_payment(
            invoice,
            payment_method_line_id=self.pad_line.id,
            l10n_ca_cpa005_transaction_code_id=self.code_pad.id,
        )
        self.assertEqual(payment.l10n_ca_cpa005_transaction_code_id, self.code_pad)

    def test_cpa005_payment_register_wizard_missing_journal_bank_account(self):
        """If journal has no bank account configured, payment register wizard displays actionable error and raises RedirectWarning on submit."""
        self.journal.bank_account_id = False
        out_invoice = self._create_invoice_one_line(price_unit=150.0, name='test line', post=True)
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=out_invoice.ids,
        ).create({
            'payment_method_line_id': self.pad_line.id,
            'l10n_ca_cpa005_transaction_code_id': self.code_pad.id,
        })
        self.assertIn('cpa005_missing_journal_bank', wizard.actionable_errors)
        # The recipient bank account is the journal one.
        self.assertFalse(wizard.show_partner_bank_account)
        self.assertFalse(wizard.require_partner_bank_account)
        with self.assertRaisesRegex(RedirectWarning, "Please set a Bank Account"):
            wizard.action_create_payments()

    def test_cpa005_payment_register_wizard_partner_bank_visibility(self):
        """The recipient bank account is hidden for inbound CPA 005 payments, but kept for outbound ones."""
        out_invoice, in_invoice = (
            self._create_invoice_one_line(move_type=move_type, price_unit=150.0, name='test line', post=True)
            for move_type in ('out_invoice', 'in_invoice')
        )

        for invoice, method_line, payment_type, expected_visibility in (
            (out_invoice, self.pad_line, 'inbound', False),
            (in_invoice, self.eft_line, 'outbound', True),
        ):
            with self.subTest(payment_type=payment_type):
                wizard = self.env['account.payment.register'].with_context(
                    active_model='account.move',
                    active_ids=invoice.ids,
                ).create({
                    'payment_method_line_id': method_line.id,
                    'l10n_ca_cpa005_transaction_code_id': self.code_pad.id,
                })
                self.assertEqual(wizard.payment_method_code, 'cpa005')
                self.assertEqual(wizard.payment_type, payment_type)
                self.assertEqual(wizard.show_partner_bank_account, expected_visibility)
                self.assertEqual(wizard.require_partner_bank_account, expected_visibility)

    def test_cpa005_batch_creation_missing_transaction_code_rejected(self):
        """Creating a batch payment with payments missing transaction codes is rejected."""
        payment = self._create_cpa005_payment(amount=100.0, l10n_ca_cpa005_transaction_code_id=False)
        batch = self._create_batch_payment(payment)
        with self.assertRaisesRegex(RedirectWarning, "Some payments have no EFT/CPA transaction code"):
            batch.validate_batch()
