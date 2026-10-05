from odoo import tools
from odoo.tests import tagged
from odoo.tests.common import freeze_time
from .common import TestDoEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time('2026-03-23')
class TestEdiXml(TestDoEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def _assert_ecf_xml(self, invoice, expected_xml_file):
        xml_bytes, error = invoice._l10n_do_edi_generate_ecf_xml(invoice.company_id)
        self.assertFalse(error, f"ECF XML generation failed: {error}")
        xml_tree = self.get_xml_tree_from_string(xml_bytes)
        with tools.file_open(f'l10n_do_edi/tests/expected_xmls/{expected_xml_file}', 'rb') as f:
            expected_tree = self.get_xml_tree_from_string(f.read())
        self.assertXmlTreeEqual(xml_tree, expected_tree)

    def test_ecf_31_structure(self):
        """
        Tests the structure of document type 31
        - One line per invoicing indicator (except non-billable and additional taxes)
        - Withholdings (ITBIS and ISR)
        - Product types: consumable (IndicadorBienoServicio=1), service (=2)
        - Tax exempt
        - Tax 0%
        """
        product_service = self.env['product.product'].create({
            'name': 'service_product',
            'type': 'service',
            'list_price': 800.0,
        })
        invoice = self._create_invoice(
            doc_type=self.doc_type_31,
            invoice_line_ids=[
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, (self.tax_18 + self.tax_withholding_itbis).ids)],
                }),
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, self.tax_16.ids)],
                }),
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, self.tax_0.ids)],
                }),
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, self.tax_exempt.ids)],
                }),
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 500.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, (self.tax_18 + self.tax_withholding_isr).ids)],
                }),
                (0, 0, {
                    'product_id': product_service.id,
                    'price_unit': 800.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, self.tax_18.ids)],
                }),
            ],
        )
        invoice.action_post()
        self._assert_ecf_xml(invoice, 'ecf_31.xml')

    def test_ecf_31_price_include(self):
        """
        Tests the structure of document type 31 with price-included taxes
        - IndicadorMontoGravado should be 1
        - MontoItem should reflect tax-included amounts
        - ITBIS withholding
        - Discount on a line
        """
        tax_18_included = self.env['account.tax'].create({
            'name': '18% ITBIS Included',
            'amount': 18,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'include_base_amount': False,
            'l10n_do_edi_invoicing_indicator': '1',
            'company_id': self.company.id,
        })
        invoice = self._create_invoice(
            doc_type=self.doc_type_31,
            invoice_line_ids=[(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 1000.0,
                'quantity': 1,
                'discount': 10.0,
                'tax_ids': [(6, 0, (tax_18_included + self.tax_withholding_itbis).ids)],
            })],
        )
        invoice.action_post()
        self._assert_ecf_xml(invoice, 'ecf_31_price_include.xml')

    def test_ecf_31_multicurrency_withholdings(self):
        """
        Tests document type 31 with multi-currency (USD) and ITBIS withholding
        - ITBIS withholding (-30%) on both lines
        - OtraMoneda node with foreign currency amounts
        - Retencion nodes on line items
        """
        invoice = self._create_invoice(
            doc_type=self.doc_type_31,
            currency_id=self.currency_usd.id,
            invoice_payment_term_id=False,
            invoice_date_due='2026-03-23',
            invoice_line_ids=[
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, (self.tax_18 + self.tax_withholding_itbis).ids)],
                }),
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 500.0,
                    'quantity': 1,
                    'tax_ids': [(6, 0, (self.tax_18 + self.tax_withholding_itbis).ids)],
                }),
            ],
        )
        invoice.action_post()
        self._assert_ecf_xml(invoice, 'ecf_31_multicurrency_withholdings.xml')

    def test_ecf_32_structure(self):
        """
        Tests the structure of document type 32
        - Foreign Partner
        - Multi-currency
        - Discount
        - Invoice Due Date not the same as invoice date
        """
        invoice = self._create_invoice(
            doc_type=self.doc_type_32,
            partner_id=self.foreign_partner.id,
            currency_id=self.currency_usd.id,
            invoice_payment_term_id=False,
            invoice_date_due='2026-03-23',
            invoice_line_ids=[(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 1000.0,
                'quantity': 1,
                'discount': 10.0,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })],
        )
        invoice.action_post()
        self._assert_ecf_xml(invoice, 'ecf_32.xml')

    def test_ecf_32_additional_taxes(self):
        """
        Tests the structure of document type 32 with additional taxes
        - Additional taxes (invoicing indicator 7) on all lines
        - Partner with no VAT
        - ImpuestosAdicionales and ImpuestosAdicionalesOtraMoneda nodes
        """
        invoice = self._create_invoice(
            doc_type=self.doc_type_32,
            partner_id=self.no_vat_partner.id,
            currency_id=self.currency_usd.id,
            invoice_payment_term_id=False,
            invoice_date_due='2026-03-23',
            invoice_line_ids=[
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 1000.0,
                    'quantity': 1,
                    'discount': 10.0,
                    'tax_ids': [(6, 0, (self.tax_18 + self.tax_additional).ids)],
                }),
                (0, 0, {
                    'product_id': self.product_a.id,
                    'price_unit': 500.0,
                    'quantity': 2,
                    'tax_ids': [(6, 0, (self.tax_18 + self.tax_additional).ids)],
                }),
            ],
        )
        invoice.action_post()
        self._assert_ecf_xml(invoice, 'ecf_32_additional_taxes.xml')

    def test_ecf_33_structure(self):
        """
        Tests the structure of document type 33 (Debit Note)
        - InformacionReferencia with debit_origin_id
        - Withholdings
        """
        origin_invoice = self._create_invoice(doc_type=self.doc_type_31)
        origin_invoice.action_post()

        debit_note = self._create_invoice(
            doc_type=self.doc_type_33,
            debit_origin_id=origin_invoice.id,
            l10n_do_edi_modification_code='3',
            ref='Correction of amounts',
            invoice_line_ids=[(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 200.0,
                'quantity': 1,
                'tax_ids': [(6, 0, (self.tax_18 + self.tax_withholding_itbis).ids)],
            })],
        )
        debit_note.action_post()
        self._assert_ecf_xml(debit_note, 'ecf_33.xml')

    def test_ecf_34_structure(self):
        """
        Tests the structure of document type 34 (Credit Note)
        - InformacionReferencia with reversed_entry_id
        - IndicadorNotaCredito
        - Withholdings
        """
        origin_invoice = self._create_invoice(doc_type=self.doc_type_31)
        origin_invoice.action_post()

        credit_note = self._create_invoice(
            doc_type=self.doc_type_34,
            move_type='out_refund',
            reversed_entry_id=origin_invoice.id,
            l10n_do_edi_modification_code='1',
            ref='Cancellation of invoice',
            invoice_line_ids=[(0, 0, {
                'product_id': self.product_a.id,
                'price_unit': 300.0,
                'quantity': 1,
                'tax_ids': [(6, 0, (self.tax_18 + self.tax_withholding_isr).ids)],
            })],
        )
        credit_note.action_post()
        self._assert_ecf_xml(credit_note, 'ecf_34.xml')
