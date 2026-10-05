from lxml import etree

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_batch_payment.models.sepa_mapping import sanitize_communication
from odoo.tests.common import test_xsd
from odoo.tests import tagged, Form


class TestSEPACreditTransferCommon(AccountTestInvoicingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.EUR').active = True

        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')

        # tests doesn't go through the sanitization (_ is invalid)
        cls.partner_a.name = sanitize_communication(cls.partner_a.name)
        cls.partner_b.name = sanitize_communication(cls.partner_b.name)

        # A country is required for sepa transfer
        cls.partner_a.country_id = cls.env.ref('base.us')
        cls.partner_b.country_id = cls.env.ref('base.us')

        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0477472701',
            'currency_id': cls.env.ref('base.EUR').id
        })

        # Create an IBAN bank account and its journal
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.bank_journal.write({
            'bank_account_number': 'BE48363523682327',
            'bank_name': 'ING',
            'bank_bic': 'BBRUBEBB',
            'currency_id': cls.env.ref('base.EUR').id,
        })
        cls.sepa_ct = cls.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'sepa_ct')
        cls.sepa_ct_method = cls.env.ref('account_iso20022.account_payment_method_sepa_ct')

        # Make sure all suppliers have exactly one bank account
        cls.env['res.partner.bank'].create({
            'partner_id': cls.partner_a.id,
            'account_number': 'BE08429863697813',
            'allow_out_payment': True,
            'bank_name': 'BNP Paribas',
            'bank_bic': 'GEBABEBB',
        })
        cls.env['res.partner.bank'].create({
            'partner_id': cls.partner_b.id,
            'account_number': '1234567890',
            'allow_out_payment': True,
            'bank_name': 'Mock & Co',
        })

    @classmethod
    def createPayment(cls, partner, amount, memo=None):
        """ Create a SEPA credit transfer payment """
        return cls.env['account.payment'].create({
            'journal_id': cls.company_data['default_journal_bank'].id,
            'currency_id': cls.env.ref('base.EUR').id,
            'payment_method_line_id': cls.sepa_ct.id,
            'payment_type': 'outbound',
            'date': '2015-04-28',
            'amount': amount,
            'partner_id': partner.id,
            'partner_type': 'supplier',
            'memo': memo,
        })


@tagged('post_install', '-at_install')
class TestSEPACreditTransfer(TestSEPACreditTransferCommon):
    _test_user_groups = None  # FIXME list needed groups

    def _get_payment_method_line(self):
        return self.bank_journal.outbound_payment_method_line_ids.filtered(lambda line: line.payment_method_id.code == 'sepa_ct')

    def test_standard_sepa(self):
        for bic in ["BBRUBEBB", False]:
            payment_1 = self.createPayment(self.partner_a, 500)
            payment_1.action_post()
            payment_2 = self.createPayment(self.partner_a, 600)
            payment_2.action_post()

            self.bank_journal.bank_account_id.bank_bic = bic
            batch = self.env['account.batch.payment'].create({
                'journal_id': self.bank_journal.id,
                'payment_ids': [(4, payment.id, None) for payment in (payment_1 | payment_2)],
                'payment_method_id': self.sepa_ct_method.id,
                'batch_type': 'outbound',
            })

            wizard_action = batch.validate_batch()
            self.assertFalse(wizard_action, "Validation wizard should not have returned an action")

            self.assertTrue(payment_1.is_sent)
            self.assertTrue(payment_2.is_sent)

    def test_sepa_pain_version(self):
        payment_method_line = self._get_payment_method_line()

        # Test to make sure the initial version is 'Generic' since it is a belgian IBAN
        self.assertEqual(payment_method_line.sepa_pain_version, 'pain.001.001.09')

        # Change IBAN prefix to Germany and check that the pain version is updated accordingly
        self.bank_journal.bank_account_id.allow_out_payment = False
        self.bank_journal.bank_account_number = 'DE89370400440532013000'
        self.assertEqual(payment_method_line.sepa_pain_version, 'pain.001.001.03.de')

        # Provide an invalid IBAN to see if the pain version falls back to the company's fiscal country
        self.bank_journal.bank_account_id.allow_out_payment = False
        self.bank_journal.bank_account_number = 'DEL48363523682327'
        self.env.company.account_fiscal_country_id = self.env.company.country_id = self.env.ref('base.at')
        self.assertEqual(payment_method_line.sepa_pain_version, 'pain.001.001.03.austrian.004')

        # Remove the company's fiscal country and verify that the pain version now corresponds to the company's country
        self.env.company.country_id = self.env.company.country_id = self.env.ref('base.de')
        self.env.company.account_fiscal_country_id = None
        self.assertEqual(payment_method_line.sepa_pain_version, 'pain.001.001.03.de')

    def test_sepa_character_conversion(self):
        """
        - Change the partner's name and street to contain non-latin characters
        - Check that communication (InstrId) is converted and trimmed to the correct unescaped size (max size = 35 characters)
        """
        self.partner_a.name = "ÀÎÑϐН"
        self.partner_a.bank_ids.sudo().allow_out_payment = False
        self.partner_a.bank_ids.holder_name = "ÀÎÑϐН"
        self.partner_a.bank_ids.sudo().allow_out_payment = True
        self.partner_a.street = "íċēķθН"
        self.partner_a.city = "City"
        self.partner_a.country_id = self.env.ref('base.be')

        payment_1 = self.createPayment(self.partner_a, 500)
        payment_1.memo = "Wynand & Olivier are great fun!"
        payment_1.action_post()
        payment_2 = self.createPayment(self.partner_a, 700)
        payment_2.action_post()

        self.bank_journal.bank_account_id.bank_bic = "BBRUBEBB"
        self._get_payment_method_line().sepa_pain_version = 'pain.001.001.03'
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [(4, payment.id, None) for payment in (payment_1 | payment_2)],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })

        wizard_action = batch.validate_batch()
        self.assertFalse(wizard_action, "Validation wizard should not have returned an action")

        ct_doc = etree.fromstring(bytes(batch.export_file))
        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'}
        name = ct_doc.findtext('.//ns:Cdtr/ns:Nm', namespaces=namespaces)
        street = ct_doc.findtext('.//ns:Cdtr/ns:PstlAdr/ns:AdrLine', namespaces=namespaces)
        InstrId = ct_doc.findtext('.//ns:InstrId', namespaces=namespaces)
        self.assertEqual(name, "AIN.N")
        self.assertEqual(street, "icekthN")
        self.assertIn("Wynand + Olivier", InstrId, "'&' should be replaced with '+' in InstrId")

    def test_sepa_with_no_end_to_end_id(self):
        """
        Test to make sure the transaction ID is generated and added to the XML even if transaction_uuid is empty.
        """

        payment = self.createPayment(self.partner_a, 500)
        payment.transaction_uuid = False
        payment.action_post()

        self.bank_journal.bank_account_id.bank_bic = "BBRUBEBB"
        self._get_payment_method_line().sepa_pain_version = 'pain.001.001.03'
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.set([payment.id])],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })

        batch.validate_batch()

        ct_doc = etree.fromstring(bytes(batch.export_file))
        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'}
        EndToEndId = ct_doc.findtext('.//ns:EndToEndId', namespaces=namespaces)
        self.assertEqual(len(EndToEndId), 32, "A 32 character UUID hex value should have been generated")

    def test_sepa_ampersand_in_partner_name(self):
        """
        '&' in partner name must be preserved as '&amp;' in the XML output (<Nm> field).
        '&' in reference/identifier fields (InstrId, Ustrd) must be replaced with '+'.
        """
        self.partner_a.name = "test & test GMBH"
        self.partner_a.bank_ids.holder_name = "test & test GMBH"
        self.partner_a.city = "City"
        self.partner_a.country_id = self.env.ref('base.be')

        payment = self.createPayment(self.partner_a, 500, memo="Invoice & Order")
        payment.action_post()

        self.bank_journal.bank_account_id.bank_bic = "BBRUBEBB"
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [(4, payment.id, None)],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })
        batch.payment_ids.payment_method_line_id.sepa_pain_version = 'pain.001.001.03'
        batch.validate_batch()

        ct_doc = etree.fromstring(bytes(batch.export_file))
        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'}
        name = ct_doc.findtext('.//ns:Cdtr/ns:Nm', namespaces=namespaces)
        ustrd = ct_doc.findtext('.//ns:Ustrd', namespaces=namespaces)
        instr_id = ct_doc.findtext('.//ns:InstrId', namespaces=namespaces)

        self.assertEqual(name, "test & test GMBH", "'&' in <Nm> must be preserved (XML-escaped to &amp; by lxml)")
        self.assertEqual(ustrd, "Invoice + Order", "'&' in <Ustrd> must be replaced with '+'")
        self.assertTrue(instr_id.endswith("-Invoice + Order"), "'&' in <InstrId> must be replaced with '+'")

    def _check_structured_reference(self, country_code, payment):
        if country_code == 'ch':
            payment.partner_bank_id.sudo().allow_out_payment = False
            payment.partner_bank_id.sanitized_account_number = 'CH4731000133285251000'
            payment.partner_bank_id.sudo().allow_out_payment = True
        payment.action_post()
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [(4, payment.id, None)],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()

        ct_doc = etree.fromstring(bytes(batch.export_file))
        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'}
        strd_cd = ct_doc.findtext('.//ns:Strd/ns:CdtrRefInf/ns:Tp/ns:CdOrPrtry/ns:Cd', namespaces=namespaces)
        strd_prtry = ct_doc.findtext('.//ns:Strd/ns:CdtrRefInf/ns:Tp/ns:CdOrPrtry/ns:Prtry', namespaces=namespaces)
        strd_issr = ct_doc.findtext('.//ns:Strd/ns:CdtrRefInf/ns:Tp/ns:Issr', namespaces=namespaces)
        strd_ref = ct_doc.findtext('.//ns:Strd/ns:CdtrRefInf/ns:Ref', namespaces=namespaces)

        if country_code == 'ch':
            self.assertEqual(strd_prtry, 'QRR')
        else:
            self.assertEqual(strd_cd, 'SCOR')

        if country_code == 'be':
            self.assertEqual(strd_issr, 'BBA')
        elif country_code == 'eu':
            self.assertEqual(strd_issr, 'ISO')

        self.assertEqual(strd_ref, payment.memo)

    def test_structured_reference_eu(self):
        payment = self.createPayment(self.partner_a, 500, 'RF18539007547034')
        self._check_structured_reference('eu', payment)

    def test_structured_reference_be(self):
        self.partner_a.country_id = self.env.ref('base.be')
        payment = self.createPayment(self.partner_a, 500, '020343057642')
        self._check_structured_reference('be', payment)

    def test_structured_reference_dk(self):
        self.partner_a.country_id = self.env.ref('base.dk')
        payment = self.createPayment(self.partner_a, 500, '+71<000000001234566+88655702<')
        self._check_structured_reference('dk', payment)

    def test_structured_reference_ch(self):
        self.partner_a.country_id = self.env.ref('base.ch')
        payment = self.createPayment(self.partner_a, 500, '000000000000000000000012371')
        self._check_structured_reference('ch', payment)

    def test_ch_qr_iban_journal_reference_with_special_chars_is_sanitized(self):
        """
        Test that the reference is sanitized when generating a
        QR-IBAN SEPA credit transfer.
        """
        self.bank_journal.bank_account_id.allow_out_payment = False
        self.bank_journal.bank_account_number = 'CH59 3007 6011 6238 5295 7'
        self.partner_a.country_id = self.env.ref('base.ch')
        ch_bank_account = self.env['res.partner.bank'].create({
            'account_number': 'CH59 3007 6011 6238 5295 7',
            'partner_id': self.partner_a.id,
            'allow_out_payment': True,
        })

        payment = self.createPayment(self.partner_a, 500, '°°°REF123°°°')
        payment.partner_bank_id = ch_bank_account
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()

        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.09'}
        ct_doc = etree.fromstring(bytes(batch.export_file))
        strd = ct_doc.findtext('.//ns:Strd/ns:CdtrRefInf/ns:Ref', namespaces=namespaces)
        self.assertEqual('000000000000000...REF123...', strd)

    def test_structured_reference_fi(self):
        self.partner_a.country_id = self.env.ref('base.fi')
        payment = self.createPayment(self.partner_a, 500, '2023000098')
        self._check_structured_reference('fi', payment)

    def test_structured_reference_no(self):
        self.partner_a.country_id = self.env.ref('base.no')
        payment = self.createPayment(self.partner_a, 500, '1234567897')
        self._check_structured_reference('no', payment)

    def test_sepa_trust_check_partner_bank_selection(self):
        """Test untrusted partner bank account warning mechanism in the payment registration wizard."""
        vendor_bill = self.init_invoice('in_invoice', partner=self.partner_a, post=True, amounts=[1000], products=[self.product_a])
        untrusted_bank = self.env['res.partner.bank'].create({
            'partner_id': self.partner_a.id,
            'account_number': 'BE12345678901234',
            'allow_out_payment': False,
            'bank_name': 'BNP Paribas',
            'bank_bic': 'GEBABEBB',
        })

        with Form(self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=vendor_bill.id
        )) as wizard_form:
            wizard_form.payment_method_line_id = self.sepa_ct
            # Selected trusted account - no warnings
            wizard_form.partner_bank_id = self.partner_a.bank_ids.filtered('allow_out_payment')[:1]
            self.assertEqual(wizard_form.untrusted_payments_count, 0)
            # Selected untrusted account - show warnings
            wizard_form.partner_bank_id = untrusted_bank
            self.assertEqual(wizard_form.untrusted_payments_count, 1)

        # Set up a second bill with the same supplier
        second_vendor_bill = self.init_invoice('in_invoice', partner=self.partner_a, post=True, amounts=[2000], products=[self.product_a])
        # Set same untrusted bank account on payments (to check untrusted_payments_count later)
        (vendor_bill + second_vendor_bill).partner_bank_id = untrusted_bank

        # Set up a third bill to pay them both in 1 wizard
        vendor_bill_installements = self.env['account.move'].create({
            # This bill has 2 installments
            'move_type': 'in_invoice',
            'partner_id': self.partner_b.id,
            'invoice_date': fields.Date.today(),
            'invoice_payment_term_id': self.env.ref('account.account_payment_term_advance_60days').id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'test product',
                'price_unit': 100,
            })]
        })
        self.partner_b.bank_ids.allow_out_payment = False
        vendor_bill_installements.action_post()

        with Form(self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=[vendor_bill.id, second_vendor_bill.id, vendor_bill_installements.id]
        )) as wizard_form:
            wizard_form.payment_method_line_id = self.sepa_ct
            # There are 4 payments as the third bill has 2 installments but we only want to count 3 as we only pay the first installment
            self.assertEqual(wizard_form.total_payments_amount, 3)
            self.assertEqual(wizard_form.untrusted_payments_count, 3)
            self.assertTrue(wizard_form.can_group_payments)
            wizard_form.group_payment = True
            # 1 payment per supplier
            self.assertEqual(wizard_form.total_payments_amount, 2)
            self.assertEqual(wizard_form.untrusted_payments_count, 2)

    def test_sepa_creditor_name_uses_commercial_for_child_contact(self):
        """ When payment.partner_id is an invoice contact, the SEPA
        Creditor Name (Cdtr/Nm) must still be the commercial partner — banks reconcile
        against the legal entity (account holder), not the contact person.
        """
        invoice_contact = self.env['res.partner'].create({
            'name': 'Billy Fox',
            'type': 'invoice',
            'parent_id': self.partner_a.id,
            'country_id': self.partner_a.country_id.id,
        })
        payment = self.createPayment(invoice_contact, 500)
        payment.action_post()

        self.bank_journal.bank_account_id.bank_bic = "BBRUBEBB"
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.set([payment.id])],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })
        batch.payment_ids.payment_method_line_id.sepa_pain_version = 'pain.001.001.03'
        batch.validate_batch()

        ct_doc = etree.fromstring(bytes(batch.export_file))
        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'}
        creditor_name = ct_doc.findtext('.//ns:Cdtr/ns:Nm', namespaces=namespaces)
        self.assertEqual(creditor_name, self.partner_a.name)

    def test_invalid_sct_partners_uses_commercial_partner(self):
        """ A payment on an invoice contact must not be flagged as invalid
        as long as its commercial parent has a valid city and country.
        """
        self.partner_a.city = 'New York'  # complete the address (country was set in setUp)
        invoice_contact = self.env['res.partner'].create({
            'name': 'Billy Fox',
            'type': 'invoice',
            'parent_id': self.partner_a.id,
        })
        payment = self.createPayment(invoice_contact, 500)
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.set([payment.id])],
            'payment_method_id': self.sepa_ct_method.id,
            'batch_type': 'outbound',
        })
        self.assertFalse(batch.sudo().invalid_sct_partners_ids)  # sudo because possibly access employee addresses


@tagged('external_l10n', 'post_install', '-at_install', '-standard')
class TestSEPACreditTransferXmlValidity(TestSEPACreditTransferCommon):
    _test_user_groups = None  # FIXME list needed groups

    @test_xsd(path='account_iso20022/schemas/pain.001.001.03.xsd')
    def test_standard_sepa(self):
        sct_docs = []
        for bic in ["BBRUBEBB", False]:
            payment_1 = self.createPayment(self.partner_a, 500)
            payment_1.action_post()
            payment_2 = self.createPayment(self.partner_a, 600)
            payment_2.action_post()

            self.bank_journal.bank_account_id.bank_bic = bic
            batch = self.env['account.batch.payment'].create({
                'journal_id': self.bank_journal.id,
                'payment_ids': [Command.set((payment_1 | payment_2).ids)],
                'payment_method_id': self.sepa_ct_method.id,
                'batch_type': 'outbound',
            })

            batch.validate_batch()
            sct_docs.append(etree.fromstring(bytes(batch.export_file)))
        return sct_docs
