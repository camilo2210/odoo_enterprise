from lxml import etree

from odoo import fields
from odoo.addons.account_sepa_direct_debit.tests.common import SDDTestCommon
from odoo.tests import tagged, test_xsd


@tagged('external_l10n', 'post_install', '-at_install', '-standard')
class SDDTestXML(SDDTestCommon):

    @test_xsd(path='account_sepa_direct_debit/schemas/pain.008.001.02.xsd')
    def test_xml_pain_008_001_02_generation(self):
        self.sdd_company_bank_journal.debit_sepa_pain_version = 'pain.008.001.02'

        xml_files = []
        for invoice in (self.invoice_agrolait, self.invoice_china_export, self.invoice_no_bic):
            payment = invoice.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')
            xml_files.append(etree.fromstring(payment.generate_xml(self.sdd_company, fields.Date.today(), True)))
        return xml_files

    @test_xsd(path='account_sepa_direct_debit/schemas/EPC131-08_2019_V1.0_pain.008.001.02.xsd')
    def test_xml_pain_008_001_02_b2b_generation(self):
        self.sdd_company_bank_journal.debit_sepa_pain_version = 'pain.008.001.02'
        self.mandate_agrolait.sdd_scheme = 'B2B'
        self.mandate_china_export.sdd_scheme = 'B2B'
        self.mandate_no_bic.sdd_scheme = 'B2B'

        xml_files = []
        for invoice in (self.invoice_agrolait, self.invoice_china_export, self.invoice_no_bic):
            payment = invoice.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')
            xml_files.append(etree.fromstring(payment.generate_xml(self.sdd_company, fields.Date.today(), True)))
        return xml_files

    @test_xsd(path='account_sepa_direct_debit/schemas/pain.008.001.08.xsd')
    def test_xml_pain_008_001_08_generation(self):
        self.sdd_company_bank_journal.debit_sepa_pain_version = 'pain.008.001.08'

        xml_files = []
        for invoice in (self.invoice_agrolait, self.invoice_china_export, self.invoice_no_bic):
            payment = invoice.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')
            xml_files.append(etree.fromstring(payment.generate_xml(self.sdd_company, fields.Date.today(), True)))

        return xml_files

    def test_sdd_header_sweden(self):
        """
        Nordea (Sweden) requires an explicit <SchmeNm><Cd>CUST</Cd></SchmeNm> node
        in InitgPty/Id/OrgId/Othr (task-6385960).
        """
        self.sdd_company_bank_journal.debit_sepa_pain_version = 'pain.008.001.08'
        nsmap = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.008.001.08'}
        payment = self.invoice_agrolait.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')

        self.sdd_company.account_fiscal_country_id = self.env.ref('base.se')
        document_se = payment.generate_xml(self.sdd_company, fields.Date.today(), True)
        self.assertTrue(
            etree.fromstring(document_se).xpath('//ns:InitgPty//ns:SchmeNm/ns:Cd[text()="CUST"]', namespaces=nsmap),
            "The SchmeNm/Cd node should be present for a Swedish company",
        )

    def test_sdd_header_italy(self):
        """
        Some Italian banks reject the SDD file when <SchmeNm> is present
        in InitgPty/Id/OrgId/Othr, so it must not be generated for IT.
        """
        self.sdd_company_bank_journal.debit_sepa_pain_version = 'pain.008.001.08'
        nsmap = {'ns': 'urn:iso:std:iso:20022:tech:xsd:pain.008.001.08'}
        payment = self.invoice_agrolait.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')

        self.sdd_company.account_fiscal_country_id = self.env.ref('base.it')
        document_it = payment.generate_xml(self.sdd_company, fields.Date.today(), True)
        self.assertFalse(
            etree.fromstring(document_it).xpath('//ns:InitgPty//ns:SchmeNm', namespaces=nsmap),
            "The SchmeNm node should not be present for an Italian company",
        )
