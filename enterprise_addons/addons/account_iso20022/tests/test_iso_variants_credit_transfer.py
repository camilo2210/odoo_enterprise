from lxml import etree
from odoo.addons.account_iso20022.tests.test_iso20022_common import TestISO20022CommonCreditTransfer
from odoo.tests import tagged
from odoo.tools.misc import file_path
from freezegun import freeze_time


@tagged('post_install', '-at_install')
class TestGermanSEPACreditTransfer(TestISO20022CommonCreditTransfer):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        company.update({
            'vat': 'DE462612124',
            'currency_id': cls.env.ref('base.EUR').id,
            'country_id': cls.env.ref('base.de').id,
            'iso20022_orgid_id': '0123456789',
        })
        res['default_journal_bank'].update({
            'bank_account_number': 'DE25500105173674149934',
            'bank_name': 'Deutsche Bank',
            'bank_bic': 'DEUTBEBE',
        })
        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_sepa_ct')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])

        cls.env.ref('base.EUR').active = True
        cls.german_partner = cls.env['res.partner'].create({
            'name': 'German Customer',
            'street': 'German Street',
            'country_id': cls.env.ref('base.de').id,
        })
        cls.german_partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'DE24500105171688544432',
            'partner_id': cls.german_partner.id,
            'bank_name': 'Deutsche Bank',
            'bank_bic': 'DEUTBEBE',
            'allow_out_payment': True,
        })

    @freeze_time('2024-03-04')
    def test_german_sct_xml(self):
        batch = self.generate_iso20022_batch_payment(self.german_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)
        xml_file_path = file_path('account_iso20022/tests/xml_files/pain.001.001.03.de.xml')
        expected_tree = etree.parse(xml_file_path)

        self.assertXmlTreeEqual(sct_doc, expected_tree.getroot())

    def test_german_sct_no_lei_in_v03(self):
        """Test that the pain.001.001.03 sepa version has not the <LEI> tag."""
        self.company_data['company'].write({
            'iso20022_lei': '529900T8BM49AURSDO55',
            'iso20022_orgid_issr': 'LEIMAN',
        })

        batch = self.generate_iso20022_batch_payment(self.german_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)

        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'}
        initg_pty = sct_doc.find('.//ns:InitgPty', namespaces=namespaces)

        expected_xml = """
            <InitgPty xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
                <Nm>Grunnings</Nm>
                <Id>
                    <OrgId>
                        <Othr>
                            <Id>0123456789</Id>
                            <Issr>LEIMAN</Issr>
                        </Othr>
                    </OrgId>
                </Id>
            </InitgPty>
        """
        expected_tree = etree.fromstring(expected_xml)
        self.assertXmlTreeEqual(initg_pty, expected_tree)


@tagged('post_install', '-at_install')
class TestAustrianSEPACreditTransfer(TestISO20022CommonCreditTransfer):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        company.update({
            'vat': 'ATU12345675',
            'currency_id': cls.env.ref('base.EUR').id,
            'country_id': cls.env.ref('base.at').id,
            'iso20022_orgid_id': '0123456789',
        })
        res['default_journal_bank'].update({
            'bank_account_number': 'AT61 5400 0825 4928 3818',
            'bank_name': 'UNICREDIT BANK AUSTRIA AG',
            'bank_bic': 'BKAUATWWXXX',
        })
        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.env.ref('base.EUR').active = True
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_sepa_ct')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])
        cls.austrian_partner = cls.env['res.partner'].create({
            'name': 'Austrian Customer',
            'street': 'Austrian Street',
            'country_id': cls.env.ref('base.at').id,
        })
        cls.austrian_partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'AT35 2060 4961 4719 6834',
            'allow_out_payment': True,
            'partner_id': cls.austrian_partner.id,
            'bank_name': 'UNICREDIT BANK AUSTRIA AG',
            'bank_bic': 'BKAUATWWXXX',
        })

    @freeze_time('2024-03-04')
    def test_austrian_sct_xml(self):
        batch = self.generate_iso20022_batch_payment(self.austrian_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)
        xml_file_path = file_path('account_iso20022/tests/xml_files/pain.001.001.03.austrian.004.xml')
        expected_tree = etree.parse(xml_file_path)
        self.assertXmlTreeEqual(sct_doc, expected_tree.getroot())

    def test_austrian_sct_no_lei_in_v03(self):
        """Test that the pain.001.001.03.austrian.004 sepa version has not the <LEI> tag."""
        self.company_data['company'].write({
            'iso20022_lei': '529900T8BM49AURSDO55',
            'iso20022_orgid_issr': 'LEIMAN',
        })

        batch = self.generate_iso20022_batch_payment(self.austrian_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)

        namespaces = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'}
        initg_pty = sct_doc.find('.//ns:InitgPty', namespaces=namespaces)

        expected_xml = """
            <InitgPty xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
                <Nm>Grunnings</Nm>
                <Id>
                    <OrgId>
                        <Othr>
                            <Id>0123456789</Id>
                        </Othr>
                    </OrgId>
                </Id>
            </InitgPty>
        """
        expected_tree = etree.fromstring(expected_xml)
        self.assertXmlTreeEqual(initg_pty, expected_tree)


@tagged('post_install', '-at_install')
class TestSwedishIsoCreditTransfer(TestISO20022CommonCreditTransfer):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        # the Swedish pain version should be able to handle empty address fields
        company.update({
            'vat': 'SE123456789701',
            'currency_id': cls.env.ref('base.SEK').id,
            'country_id': cls.env.ref('base.se').id,
            'street': '',
            'city': '',
            'zip': '',
            'iso20022_orgid_id': '0123456789',
        })
        res['default_journal_bank'].update({
            'bank_account_number': 'SE7335536296831513338982',
            'bank_name': 'SwedBank',
            'bank_bic': 'SWEDSESS',
        })
        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.env.ref('base.SEK').active = True
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_iso20022_se')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])

        cls.swedish_partner = cls.env['res.partner'].create({
            'name': 'Swedish Partner',
            'street': 'Swedish Street',
            'country_id': cls.env.ref('base.se').id,
        })
        cls.swedish_partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'SE4550000000058398257466',
            'allow_out_payment': True,
            'partner_id': cls.swedish_partner.id,
            'bank_name': 'Swedbank',
        })
        cls.swedish_iso_pay_method = cls.company_data['default_journal_bank'].outbound_payment_method_line_ids.filtered(
            lambda l: l.code == 'iso20022_se')
        cls.swedish_iso_pay_method = cls.env.ref('account_iso20022.account_payment_method_iso20022_se')

    @freeze_time('2024-03-04')
    def test_swedish_iso_xml(self):
        if self.env['ir.module.module']._get('l10n_se_bban').state == 'installed':
            self.skipTest("This test will fail if l10n_se_bban is installed.")

        for pain_version in ('pain.001.001.03', 'pain.001.001.09'):
            self.company_data['default_journal_bank'].outbound_payment_method_line_ids.sepa_pain_version = pain_version
            batch = self.generate_iso20022_batch_payment(self.swedish_partner)
            sct_doc = self.get_sct_doc_from_batch(batch)
            xml_file_path = file_path(f'account_iso20022/tests/xml_files/{pain_version}.se.xml')
            expected_tree = etree.parse(xml_file_path)

            self.assertXmlTreeEqual(sct_doc, expected_tree.getroot())


@tagged('post_install', '-at_install')
class TestSwissIsoCreditTransfer(TestISO20022CommonCreditTransfer):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        company.update({
            'country_id': cls.env.ref('base.ch').id,
            'vat': 'CHE-530781296TVA',
            'currency_id': cls.env.ref('base.CHF').id,
            'iso20022_orgid_id': '0123456789'
        })
        res['default_journal_bank'].update({
            'bank_account_number': 'CH4431999123000889012',
            'bank_name': 'ONE SWISS BANK SA',
            'bank_bic': 'BQBHCHGG',
        })
        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.env.ref('base.CHF').active = True

        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_iso20022_ch')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])

        cls.swiss_partner = cls.env['res.partner'].create({
            'name': 'Easy Clean Lausanne',
            'street': 'Rte de Prilly 18',
            'zip': 1004,
            'city': 'Lausanne',
            'country_id': cls.env.ref('base.ch').id,
        })
        cls.swiss_partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'CH11 3000 5228 1308 3501 F',
            'allow_out_payment': True,
            'partner_id': cls.swiss_partner.id,
            'bank_name': 'swiss_bank',
            'bank_bic': 'BQBHCHGG',
            'clearing_label_id': cls.env.ref('base.clearing_label_all').id,
            'clearing_number': '123456',
        })

    @freeze_time('2024-03-04')
    def test_swiss_iso_xml_pain_03(self):
        self.company_data['default_journal_bank'].outbound_payment_method_line_ids.sepa_pain_version = 'pain.001.001.03'
        batch = self.generate_iso20022_batch_payment(self.swiss_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)
        xml_file_path = file_path('account_iso20022/tests/xml_files/pain.001.001.03.ch.02.xml')
        expected_tree = etree.parse(xml_file_path)
        self.assertXmlTreeEqual(sct_doc, expected_tree.getroot())

    @freeze_time('2024-03-04')
    def test_swiss_iso_xml_pain_09(self):
        batch = self.generate_iso20022_batch_payment(self.swiss_partner, memo="210000000003139471430009017")
        sct_doc = self.get_sct_doc_from_batch(batch)
        xml_file_path = file_path('account_iso20022/tests/xml_files/pain.001.001.09.ch.03.xml')
        expected_tree = etree.parse(xml_file_path)
        self.assertXmlTreeEqual(sct_doc, expected_tree.getroot())


@tagged('post_install', '-at_install')
class TestAmericanISOCreditTransfer(TestISO20022CommonCreditTransfer):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        company.update({
            'iso20022_orgid_id': '0123456789',
            'iso20022_initiating_party_name': 'US Company',
            'iso20022_orgid_issr': 'USABA',
        })
        res['default_journal_bank'].update({
            'bank_account_number': '7896541230',
            'bank_name': 'Bank of America',
            'bank_bic': 'BOFAUS3NXXX',
        })
        res['default_journal_bank'].bank_account_id.update({
            'clearing_label_id': cls.env.ref('base.clearing_label_us').id,
            'clearing_number': '011900254',
        })

        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_iso20022_us')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])

        cls.env.ref('base.USD').active = True
        cls.american_partner = cls.env['res.partner'].create({
            'name': 'American Customer',
            'street': 'American Street',
            'country_id': cls.env.ref('base.us').id,
        })
        cls.american_partner_bank = cls.env['res.partner.bank'].create({
            'account_number': '9632587410',
            'clearing_label_id': cls.env.ref('base.clearing_label_us').id,
            'clearing_number': '322271627',
            'partner_id': cls.american_partner.id,
            'bank_name': 'Bank of America',
            'bank_bic': 'BOFAUS3NXXX',
            'country_id': cls.env.ref('base.us').id,
            'allow_out_payment': True,
        })

    @freeze_time('2024-03-04')
    def test_us_ach_iso_xml(self):
        batch = self.generate_iso20022_batch_payment(self.american_partner)
        sct_doc = self.get_sct_doc_from_batch(batch)
        xml_file_path = file_path('account_iso20022/tests/xml_files/pain.001.001.03.us.xml')
        expected_tree = etree.parse(xml_file_path)

        self.assertXmlTreeEqual(sct_doc, expected_tree.getroot())
