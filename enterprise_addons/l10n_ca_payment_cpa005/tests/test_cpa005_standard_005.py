from odoo.tests import tagged

from odoo.addons.l10n_ca_payment_cpa005.tests.common import CPA005Common


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCPA005Standard005(CPA005Common):
    """Conformance of the field positions/contents against Payments Canada Standard 005.

    Field values below reproduce the illustrative examples for Logical Record Types C and D
    given in Standard 005, Section D, Appendix 1 (Data Element Dictionary) and Section D pages
    6 and 8 (sample segment inputs).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Match the Originator's Short/Long Name and User's ID used in the Standard 005 examples.
        cls.partner_a.name = 'Tim Jones'
        cls.company.write({
            'l10n_ca_cpa005_short_name': 'CANADIANCO',
            'name': 'CANADIAN COMPUTER COMPANY',
        })
        cls.journal.l10n_ca_cpa005_originator_id = 'TWCMS10201'
        # comp_bank_account1 is already trusted, sudo to bypass the lock
        cls.comp_bank_account1.sudo().write({
            'account_number': '01111122222',
            'l10n_ca_financial_institution_number': '000410202',
        })
        cls.counterparty_bank = cls._create_ca_bank(
            partner_id=cls.partner_a,
            account_number='4004777777',
            l10n_ca_financial_institution_number='061400152',
            sequence=5,  # Makes it the principal account if other accounts already exists
        )
        # Collecting a PAD requires the payor's consent
        cls.mandate = cls._create_cpa005_mandate(partner_bank_id=cls.counterparty_bank, start_date='2023-01-01')
        transaction_codes = cls.env['l10n_ca_cpa005.transaction.code']
        cls.code_d = transaction_codes.search([('code', '=', '370')], limit=1)
        cls.code_c = transaction_codes.search([('code', '=', '200')], limit=1)
        # Day 274 of 2023 == 2023-10-01 -> "0YYDDD" == "023274" in the example
        cls.example_date = '2023-10-01'
        cls.origination_control_data = f"{cls.journal.l10n_ca_cpa005_originator_id:10.10}0001"

    def _assert_header(self, header):
        self.assertEqual(header[0], 'A', "A.01 Logical Record Type ID")
        self.assertEqual(header[1:10], '000000001', "A.02 Logical Record Count")
        self.assertEqual(header[10:20], self.journal.l10n_ca_cpa005_originator_id, "A.03 Originator's ID")
        self.assertEqual(header[20:24], '0001', "A.04 File Creation No.")
        self.assertEqual(header[24:30], '023274', "A.05 Creation Date")
        self.assertEqual(header[30:35], self.journal.l10n_ca_cpa005_destination_data_center, "A.06 Destination Data Centre")
        self.assertEqual(header[35:55], ' ' * 20, "A.07 Reserved Customer - Direct Clearer Communication Area")
        self.assertEqual(header[55:58], 'CAD', "A.08 Currency Code Identifier")
        self.assertEqual(header[58:1464], ' ' * 1406, "A.09 Filler")

    def _assert_footer(self, footer, record_type):
        debit_value, debit_count, credit_value, credit_count = (
            ('00000000000000', '00000000', '00000000030000', '00000001')
            if record_type == 'C' else
            ('00000000030000', '00000001', '00000000000000', '00000000')
        )
        self.assertEqual(footer[0], 'Z', "Z.01 Logical Record Type ID")
        self.assertEqual(footer[1:10], '000000003', "Z.02 Logical Record Count")
        self.assertEqual(footer[10:24], self.origination_control_data, "Z.03 Origination Control Data")
        self.assertEqual(footer[24:38], debit_value, "Z.04 Total Value of Debit Transactions")
        self.assertEqual(footer[38:46], debit_count, "Z.05 Total Number of Debit Transactions")
        self.assertEqual(footer[46:60], credit_value, "Z.06 Total Value of Credit Transactions")
        self.assertEqual(footer[60:68], credit_count, "Z.07 Total Number of Credit Transactions")
        self.assertEqual(footer[68:82], '00000000000000', "Z.08 Total Value of Error Corrections 'E'")
        self.assertEqual(footer[82:90], '00000000', "Z.09 Total Number of Error Corrections 'E'")
        self.assertEqual(footer[90:104], '00000000000000', "Z.10 Total Value of Error Corrections 'F'")
        self.assertEqual(footer[104:112], '00000000', "Z.11 Total Number of Error Corrections 'F'")
        self.assertEqual(footer[112:1464], ' ' * 1352, "Z.12 Filler")

    def _assert_common_segment(self, record, record_type, payment):
        # Positions from Standard 005 Section D (shared for records Type C and D), 1-indexed.
        self.assertEqual(record[0], record_type, "C/D.01 Logical Record Type ID")
        self.assertEqual(record[1:10], '000000002', "C/D.02 Logical Record Count")
        self.assertEqual(record[10:24], self.origination_control_data, "C/D.03 Origination Control Data")
        self.assertEqual(record[24:27], '200' if record_type == 'C' else '370', "C/D.04 Transaction Type")
        self.assertEqual(record[27:37], '0000030000', "C/D.05 Amount (cents, 10, zero-filled)")
        self.assertEqual(record[37:43], '023274', "C/D.06 Date Funds to be Available / Due Date (0YYDDD)")
        self.assertEqual(record[43:52], '061400152', "C/D.07 Institutional Identification No.")
        self.assertEqual(record[52:64].strip(), '4004777777', "C/D.08 Payee/Payor Account No.")
        self.assertEqual(record[64:86], f"{payment.id:022d}", "C/D.09 Item Trace No.")
        self.assertEqual(record[86:89], '000', "C/D.10 Stored Transaction Type")
        self.assertEqual(record[89:104].strip(), 'CANADIANCO', "C/D.11 Originator's Short Name")
        self.assertEqual(record[104:134].strip(), 'Tim Jones', "C/D.12 Payee/Payor Name")
        self.assertEqual(record[134:164].strip(), 'CANADIAN COMPUTER COMPANY', "C/D.13 Originator's Long Name")
        self.assertEqual(record[164:174].strip(), 'TWCMS10201', "C/D.14 Originating Direct Clearer's User's ID")
        self.assertEqual(record[174:193].strip(), 'AR0545', "C/D.15 Originator's Cross Reference No.")
        self.assertEqual(record[193:202], '000410202', "C/D.16 Institutional ID Number for Returns")
        self.assertEqual(record[202:214].strip(), '01111122222', "C/D.17 Account No. for Returns")
        self.assertEqual(record[214:229], ' ' * 15, "C/D.18 Originator's Sundry Information")
        self.assertEqual(record[229:251], ' ' * 22, "C/D.19 Filler")
        self.assertEqual(record[251:253], ' ' * 2, "C/D.20 Originator-Direct Clearer Settlement Code")
        self.assertEqual(record[253:264], '00000000000', "C/D.21 Invalid Data Element ID (zeros)")

    def test_record_c(self):
        record_type = 'C'
        payment = self._create_cpa005_payment(
            payment_type='outbound',
            partner_id=self.partner_a,
            l10n_ca_cpa005_transaction_code_id=self.code_c,
            amount=300.00,
            date=self.example_date,
            payment_reference='AR0545',
        )
        batch = self._create_batch_payment(payment, 'outbound', date=self.example_date)
        lines = batch._generate_cpa005_file().splitlines()
        self.assertEqual(len(lines), 3)
        header, record, footer = lines
        self.assertEqual(len(record), 1464)

        # Header (Record A)
        self._assert_header(header)
        # Transaction (Record C)
        self._assert_common_segment(record, record_type, payment)
        # Footer (Record Z)
        self._assert_footer(footer, record_type)

    def test_record_d(self):
        record_type = 'D'
        payment = self._create_cpa005_payment(
            payment_type='inbound',
            partner_id=self.partner_a,
            l10n_ca_cpa005_transaction_code_id=self.code_d,
            amount=300.00,
            date=self.example_date,
            payment_reference='AR0545',
        )
        batch = self._create_batch_payment(payment, date=self.example_date)
        lines = batch._generate_cpa005_file().splitlines()
        self.assertEqual(len(lines), 3)
        header, record, footer = lines
        self.assertEqual(len(record), 1464)

        # Header (Record A)
        self._assert_header(header)
        # Transaction (Record D)
        self._assert_common_segment(record, record_type, payment)
        # Footer (Record Z)
        self._assert_footer(footer, record_type)
