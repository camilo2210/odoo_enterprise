# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.tests import tagged, freeze_time
from odoo.addons.l10n_ca_payment_cpa005.tests.common import CPA005Common


@tagged("post_install_l10n", "post_install", "-at_install")
@freeze_time("2020-11-30 19:45:00")
class TestCPA005EFT(CPA005Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal.l10n_ca_cpa005_fcn_number_next = 103

        transaction_codes = cls.env["l10n_ca_cpa005.transaction.code"]
        code_430 = transaction_codes.search([("code", "=", "430")], limit=1)
        code_200 = transaction_codes.search([("code", "=", "200")], limit=1)
        cls.batch = cls._create_batch_payment(
            cls._create_eft_payment(code_430, cls.partner_a, cls.bank_partner_a, 123.45, "partner_a_1")
            | cls._create_eft_payment(code_430, cls.partner_a, cls.bank_partner_a, 543.21, "partner_a_2")
            | cls._create_eft_payment(code_430, cls.partner_b, cls.bank_partner_b, 456.78, "partner_b_1", days_from_now=1)
            | cls._create_eft_payment(code_200, cls.partner_b, cls.bank_partner_b, 567.89, "partner_b_2"),
            "outbound",
        )

    @classmethod
    def _create_eft_payment(cls, transaction_code, partner, partner_bank, amount, memo, days_from_now=0):
        return cls._create_cpa005_payment(
            payment_type="outbound",
            l10n_ca_cpa005_transaction_code_id=transaction_code,
            partner_id=partner,
            partner_bank_id=partner_bank,
            amount=amount,
            memo=memo,
            date=fields.Date.add(fields.Date.today(), days=days_from_now),
        )

    def test_cpa005_eft(self):
        self.maxDiff = None  # show full diff in case of errors
        self.company.sudo().write({"name": "Long Compàny Nàme"})
        expected_item_trace_numbers = [f"{payment.id:022d}" for payment in self.batch.payment_ids.sorted()]
        expected = [
            # A record ("header")
            "A0000000011234567890010302033501600                    CAD                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              ",
            # C records ("outgoing payments")
            f"C000000002123456789001034300000045678020336077788888444444444   {expected_item_trace_numbers[0]}000COMP_NAME      partner_b                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            f"C000000003123456789001032000000056789020335077788888444444444   {expected_item_trace_numbers[1]}000COMP_NAME      partner_b                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            f"C000000004123456789001034300000054321020335055566666333333333   {expected_item_trace_numbers[2]}000COMP_NAME      partner_a                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            f"C000000005123456789001034300000012345020335055566666333333333   {expected_item_trace_numbers[3]}000COMP_NAME      partner_a                     Long Company Name             1234567890                   0222333339999999                                            00000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                ",
            # Z record ("footer")
            "Z000000006123456789001030000000000000000000000000000001691330000000400000000000000000000000000000000000000000000                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        ",
        ]

        for line in expected:
            self.assertEqual(
                len(line), 1464, "Every line in our CPA file should have 1464 characters (excluding \\r\\n)."
            )

        self.assertEqual(
            len(expected),
            len(self.batch.payment_ids) + 2,
            "There should be an A record, one C record per payment and one Z record.",
        )

        generated = self.batch._generate_cpa005_file()
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

    def test_cpa005_rollover_step_1(self):
        self.journal.l10n_ca_cpa005_fcn_number_next = 9999
        self.assertEqual(
            self.journal._l10n_ca_cpa005_next_file_creation_nr(), "9999", "FCN different from what was set."
        )
        self.assertEqual(self.journal._l10n_ca_cpa005_next_file_creation_nr(), "0001", "FCN should have rolled over back to 0001.")

    def test_cpa005_rollover_step_10(self):
        self.journal.l10n_ca_cpa005_fcn_number_next = 9991
        self.journal.l10n_ca_cpa005_fcn_sequence_id.sudo().number_increment = 10
        self.assertEqual(
            self.journal._l10n_ca_cpa005_next_file_creation_nr(), "9991", "FCN different from what was set."
        )
        self.assertEqual(self.journal._l10n_ca_cpa005_next_file_creation_nr(), "0002", "FCN should have rolled over back to 0002.")
