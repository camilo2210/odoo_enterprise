from lxml import etree
from odoo import Command
from odoo.addons.account_iso20022.tests.test_iso20022_common import TestISO20022CommonCreditTransfer
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestISO20022GeneralCreditTransfer(TestISO20022CommonCreditTransfer):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        res['default_journal_bank'].update({
            'bank_account_number': 'BE68539007547034',
        })
        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.JPY').active = True
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_iso20022')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': 'International Credit Transfer',
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])
        cls.generic_partner = cls.env['res.partner'].create({
            'name': 'Generic ISO20022 Partner',
            'street': '1 Test Street',
            'city': 'Brussels',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.env['res.partner.bank'].create({
            'account_number': 'BE08429863697813',
            'partner_id': cls.generic_partner.id,
            'allow_out_payment': True,
        })

    def test_iso_20022_currency_decimal_formatting(self):
        """
        Test that currencies with 0 decimal places (like JPY) are formatted
        as integers in the XML (e.g., '1000' instead of '1000.00').
        """
        partner_jp = self.env['res.partner'].create({
            'name': 'Japanese Partner',
            'country_id': self.env.ref('base.jp').id,
        })

        partner_bank = self.env['res.partner.bank'].create({
            'account_number': 'JP1234567890',
            'partner_id': partner_jp.id,
            'allow_out_payment': True,
        })

        payment = self.env['account.payment'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_method_line_id': self.payment_method_line.id,
            'payment_type': 'outbound',
            'date': '2024-03-04',
            'amount': 1000.0,
            'currency_id': self.env.ref('base.JPY').id,
            'partner_id': partner_jp.id,
            'partner_type': 'supplier',
            'partner_bank_id': partner_bank.id,
        })
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_ids': [(4, payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
            'iso20022_batch_booking': True,
        })
        batch._send_after_validation()

        xml_doc = etree.fromstring(bytes(batch.export_file))
        ns = {'ns': next(iter(xml_doc.nsmap.values()))}

        amount_node = xml_doc.find('.//ns:InstdAmt', namespaces=ns)
        self.assertEqual(amount_node.text, '1000')
        self.assertEqual(amount_node.attrib['Ccy'], 'JPY')

    def test_norm_priority_produces_consistent_svc_lvl(self):
        """
        Regression: default NORM priority must produce NORM in <InstrPrty>
        and NURG in <SvcLvl><Cd>. Before the fix SvcLvl was hardcoded to
        NURG, which could contradict a different InstrPrty value.
        """
        batch = self.generate_iso20022_batch_payment(self.generic_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)
        self.assertEqual(sct_doc.find('.//{*}PmtTpInf/{*}InstrPrty').text, 'NORM')
        self.assertEqual(sct_doc.find('.//{*}PmtTpInf/{*}SvcLvl/{*}Cd').text, 'NURG')

    def test_high_priority_produces_urgp_svc_lvl(self):
        """
        Regression: HIGH priority must produce URGP in <SvcLvl><Cd>.
        Before the fix NURG was always hardcoded, causing a fatal bank
        processing error when InstrPrty was urgent but SvcLvl said non-urgent.
        """
        payment = self.create_payment(
            self.company_data['default_journal_bank'],
            self.generic_partner,
            self.payment_method,
            100,
        )
        payment.iso20022_priority = 'HIGH'
        payment.action_post()
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch._send_after_validation()
        sct_doc = self.get_sct_doc_from_batch(batch)
        self.assertEqual(sct_doc.find('.//{*}PmtTpInf/{*}InstrPrty').text, 'HIGH')
        self.assertEqual(sct_doc.find('.//{*}PmtTpInf/{*}SvcLvl/{*}Cd').text, 'URGP')
