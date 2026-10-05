# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.tests import tagged
from odoo.tools import file_open
from .common import TestPeEdiCommon

from freezegun import freeze_time
from lxml import etree


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEdiXmls(TestPeEdiCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_price_amount_rounding(self):
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(invoice_line_ids=[(0, 0, {
                'product_id': self.product.id,
                'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                'price_unit': 83.6,  # We will compute 250.8 / 3, which results in 83.60000000000001. It must be rounded.
                'quantity': 3,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })])
            move.action_post()
            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            etree = self.get_xml_tree_from_string(edi_xml)
            price_amount = etree.find('.//{*}InvoiceLine/{*}Price/{*}PriceAmount')
            self.assertEqual(price_amount.text, '83.6')

    def test_invoice_simple_case(self):
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe()
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)
            expected_etree = self.get_xml_tree_from_string(self.expected_invoice_xml_values)
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_address_nodes(self):
        """ The address must set the district as cbc:District and the street2 as
        cbc:CitySubdivisionName, and must not set cbc:PostalZone (UBL 2.1 / SUNAT). """
        self.partner_a.write({
            'street': 'Av. test 123',
            'street2': 'Urb. test',
            'zip': '15001',
            'l10n_pe_district': self.env.ref('l10n_pe.district_pe_150101').id,
        })
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe()
            move.action_post()
            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()

        invoice_etree = self.get_xml_tree_from_string(edi_xml)
        address_node = invoice_etree.find('.//{*}AccountingCustomerParty//{*}PostalAddress')
        expected_address = self.get_xml_tree_from_string(b'''
            <cac:PostalAddress
                xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
                <cbc:ID>150101</cbc:ID>
                <cbc:StreetName>Av. test 123</cbc:StreetName>
                <cbc:CitySubdivisionName>Urb. test</cbc:CitySubdivisionName>
                <cbc:District>Lima</cbc:District>
                <cac:Country>
                    <cbc:IdentificationCode>PE</cbc:IdentificationCode>
                    <cbc:Name>Peru</cbc:Name>
                </cac:Country>
            </cac:PostalAddress>
        ''')
        self.assertXmlTreeEqual(address_node, expected_address)

    def test_refund_simple_case(self):
        with freeze_time(self.frozen_today):
            move = self._create_refund()
            (move.reversed_entry_id + move).action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)
            expected_etree = self.get_xml_tree_from_string(self.expected_refund_xml_values)
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_debit_note_simple_case(self):
        with freeze_time(self.frozen_today):
            move = self._create_debit_note()
            (move.debit_origin_id + move).action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)
            expected_etree = self.get_xml_tree_from_string(self.expected_debit_note_xml_values)
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_payment_term_detraction_case(self):
        """ Invoice in USD with detractions and multiple payment term lines"""
        self.product.l10n_pe_withhold_percentage = 10
        self.product.l10n_pe_withhold_code = '001'
        with freeze_time(self.frozen_today):
            update_vals_dict = {"l10n_pe_edi_operation_type": "1001",
                                "invoice_payment_term_id": self.env.ref("account.account_payment_term_advance_60days").id}
            invoice = self._create_invoice_pe(**update_vals_dict).with_context(edi_test_mode=True)
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)

        with file_open('l10n_pe_edi/tests/test_files/invoice_detraction_payment_terms.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_detraction_with_decimal(self):
        """ Invoice in PEN with detraction containing decimal digits"""
        self.product.l10n_pe_withhold_percentage = 10
        self.product.l10n_pe_withhold_code = '019'

        with freeze_time(self.frozen_today):
            vals = {
                'name': 'F FFI-%s1' % self.time_name,
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'invoice_payment_term_id': self.env.ref("account.account_payment_term_end_following_month").id,
                'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
                'l10n_pe_edi_operation_type': '1001',
                'invoice_line_ids': [Command.create({
                    'product_id': self.product.id,
                    'price_unit': 990.0,
                    'quantity': 1,
                    'tax_ids': [Command.set(self.tax_18.ids)],
                })],
            }
            invoice = self.env['account.move'].create(vals).with_context(edi_test_mode=True)
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)

        with file_open('l10n_pe_edi/tests/test_files/invoice_detraction_with_decimal.xml', 'rb') as expected_invoice_file:
            expected_etree = self.get_xml_tree_from_string(expected_invoice_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_detraction_usd_company_currency(self):
        """ Invoice in USD with detraction when company currency is also USD (not PEN).
        The detraction cbc:Amount must still be in PEN, converted via the exchange rate. """
        self.product.l10n_pe_withhold_percentage = 10
        self.product.l10n_pe_withhold_code = '019'

        with freeze_time(self.frozen_today):
            self.company_data['company'].currency_id = self.other_currency
            vals = {
                'name': 'F FFI-%s1' % self.time_name,
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'currency_id': self.other_currency.id,
                'invoice_payment_term_id': self.env.ref("account.account_payment_term_end_following_month").id,
                'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
                'l10n_pe_edi_operation_type': '1001',
                'invoice_line_ids': [Command.create({
                    'product_id': self.product.id,
                    'price_unit': 990.0,
                    'quantity': 1,
                    'tax_ids': [Command.set(self.tax_18.ids)],
                })],
            }
            invoice = self.env['account.move'].create(vals).with_context(edi_test_mode=True)
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)

        with file_open('l10n_pe_edi/tests/test_files/invoice_detraction_with_decimal_foreign_currency.xml', 'rb') as expected_invoice_file:
            expected_etree = self.get_xml_tree_from_string(expected_invoice_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_detraction_with_decimal_foreign_currency(self):
        """ Invoice in USD with detraction containing decimal digits"""
        self.product.l10n_pe_withhold_percentage = 10
        self.product.l10n_pe_withhold_code = '019'

        with freeze_time(self.frozen_today):
            vals = {
                'name': 'F FFI-%s1' % self.time_name,
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'currency_id': self.other_currency.id,
                'invoice_payment_term_id': self.env.ref("account.account_payment_term_end_following_month").id,
                'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
                'l10n_pe_edi_operation_type': '1001',
                'invoice_line_ids': [Command.create({
                    'product_id': self.product.id,
                    'price_unit': 990.0,
                    'quantity': 1,
                    'tax_ids': [Command.set(self.tax_18.ids)],
                })],
            }
            invoice = self.env['account.move'].create(vals).with_context(edi_test_mode=True)
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)

        with file_open('l10n_pe_edi/tests/test_files/invoice_detraction_with_decimal_foreign_currency.xml', 'rb') as expected_invoice_file:
            expected_etree = self.get_xml_tree_from_string(expected_invoice_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_low_unit_price_with_higher_decimal_precision(self):
        """ Invoice with a decimal precition of 4 digits for the product price
            and a non-zero unit price that is rounded to 0.00 in the decimal
            precision of the currency.
        """
        self.env.ref('product.decimal_price').digits = 4
        self.currency.rounding = 0.01
        with freeze_time(self.frozen_today):
            invoice_line_vals = {
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 0.0045,
                        'quantity': 100,
                        'tax_ids': [Command.set(self.tax_18.ids)],
                    })
                ],
            }
            move = self._create_invoice_pe(**invoice_line_vals)
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)

            with file_open('l10n_pe_edi/tests/test_files/invoice_low_unit_price.xml', 'rb') as expected_file:
                expected_etree = self.get_xml_tree_from_string(expected_file.read())

            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_free(self):
        """ Test the UBL generated for an invoice that uses the '18% Free' tax
        (feature introduced in enterprise#56767)
        """
        tax_18_free = self.env['account.chart.template'].ref('tax_free_group')
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(
                l10n_pe_edi_legend='1002',
                invoice_line_ids=[(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                    'price_unit': 2000.0,
                    'quantity': 5,
                    'discount': 20.0,
                    'tax_ids': [(6, 0, tax_18_free.ids)],
                })],
            )
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)

            with file_open('l10n_pe_edi/tests/test_files/invoice_free.xml', 'rb') as expected_file:
                expected_etree = self.get_xml_tree_from_string(expected_file.read())

            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_isc(self):
        """ Test the UBL generated for an invoice that uses both the ISC and the IGV taxes.
        (feature introduced in enterprise#35280)
        """
        tax_isc = self._create_isc_tax('tax_ics_20', isc_type='01', amount=20)
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(
                invoice_line_ids=[
                    (0, 0, {
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 2000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'tax_ids': [(6, 0, [tax_isc.id, self.tax_18.id])],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 2000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'tax_ids': [(6, 0, [self.tax_18.id])],
                    })
                ],
            )
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)

            with file_open('l10n_pe_edi/tests/test_files/invoice_isc.xml', 'rb') as expected_file:
                expected_etree = self.get_xml_tree_from_string(expected_file.read())
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_isc_fixed_amount(self):
        """ Test the UBL generated for an invoice that uses ISC tipo 02 (fixed amount per unit).
        ISC = 10 USD x 50 units = 500.00
        IGV = (5000 + 500) x 18% = 990.00
        Total = 6490.00
        """
        tax_isc_fixed = self._create_isc_tax('tax_isc_fixed_10', isc_type='02', amount=10, amount_type='fixed')
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(
                invoice_line_ids=[
                    (0, 0, {
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 100.0,
                        'quantity': 50,
                        'tax_ids': [(6, 0, [tax_isc_fixed.id, self.tax_18.id])],
                    }),
                ],
            )
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)

            with file_open('l10n_pe_edi/tests/test_files/invoice_isc_fixed_amount.xml', 'rb') as expected_file:
                expected_etree = self.get_xml_tree_from_string(expected_file.read())
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_isc_mixed_types(self):
        """ Invoice combining ISC tipo 01 (percent) and tipo 02 (fixed) on
        different lines. Both share TaxScheme/ID 2000, so SUNAT rule 3068
        requires merging them into a single TaxSubtotal at document level.
        TierRange/Percent must be omitted at doc level since the aggregated
        value cannot represent both tipos. """
        tax_isc_percent = self._create_isc_tax('tax_isc_17', isc_type='01', amount=17)
        tax_isc_fixed = self._create_isc_tax('tax_isc_fixed_2_70', isc_type='02', amount=2.70, amount_type='fixed')
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(
                invoice_line_ids=[
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 100.0,
                        'quantity': 13,
                        'tax_ids': [(6, 0, [tax_isc_percent.id, self.tax_18.id])],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 100.0,
                        'quantity': 2,
                        'tax_ids': [(6, 0, [tax_isc_fixed.id, self.tax_18.id])],
                    }),
                ],
            )
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)

            # Check the document-level TaxTotal directly: TaxScheme/ID=2000
            # must appear exactly once (SUNAT rule 3068) and the merged ISC
            # TaxCategory must omit TierRange/Percent.
            ns = {
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            }
            doc_tax_total = current_etree.find('cac:TaxTotal', ns)
            isc_subtotals = [
                st for st in doc_tax_total.findall('cac:TaxSubtotal', ns)
                if st.find('cac:TaxCategory/cac:TaxScheme/cbc:ID', ns).text == '2000'
            ]
            self.assertEqual(len(isc_subtotals), 1, "ISC must appear once at document level (SUNAT 3068)")
            isc_category = isc_subtotals[0].find('cac:TaxCategory', ns)
            self.assertIsNone(isc_category.find('cbc:TierRange', ns))
            self.assertIsNone(isc_category.find('cbc:Percent', ns))
            # Merged TaxAmount sums both tipos: 13*100*17% + 2*2.70 = 221 + 5.40
            self.assertEqual(isc_subtotals[0].find('cbc:TaxAmount', ns).text, '226.40')

            # Each invoice line keeps its own ISC TierRange — only doc-level merges.
            line_tier_ranges = [
                st.find('cac:TaxCategory/cbc:TierRange', ns).text
                for line in current_etree.findall('cac:InvoiceLine', ns)
                for st in line.findall('cac:TaxTotal/cac:TaxSubtotal', ns)
                if st.find('cac:TaxCategory/cac:TaxScheme/cbc:ID', ns).text == '2000'
            ]
            self.assertEqual(sorted(line_tier_ranges), ['01', '02'])

    def test_invoice_isc_with_exo_line(self):
        """ Invoice mixing an ISC-bearing line (tipo 02 fixed amount) with an
        independent EXO (exonerado) line. SUNAT rule 2999 forbids negative
        TaxableAmount at document totals: the EXO TaxSubtotal must keep its
        own base intact instead of being deflated by the ISC contribution
        from the other line. """
        chart = self.env['account.chart.template']
        tax_isc_fixed = self._create_isc_tax('tax_isc_fixed_2_70', isc_type='02', amount=2.70, amount_type='fixed')
        tax_exo = self.env['account.tax'].create({
            'name': 'tax_exo_0',
            'amount_type': 'percent',
            'amount': 0,
            'l10n_pe_edi_tax_code': '9997',
            'l10n_pe_edi_unece_category': 'E',
            'l10n_pe_edi_affectation_reason': '20',
            'type_tax_use': 'sale',
            'tax_group_id': chart.ref('tax_group_exo').id,
        })
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(
                invoice_line_ids=[
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 100.0,
                        'quantity': 2,
                        'tax_ids': [(6, 0, [tax_isc_fixed.id, self.tax_18.id])],
                    }),
                    (0, 0, {
                        'product_id': self.product.id,
                        'price_unit': 83.6,
                        'quantity': 1,
                        'tax_ids': [(6, 0, [tax_exo.id])],
                    }),
                ],
            )
            move.action_post()

            edi_xml, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)
            ns = {
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            }
            doc_tax_total = current_etree.find('cac:TaxTotal', ns)
            taxable_by_scheme = {
                st.find('cac:TaxCategory/cac:TaxScheme/cbc:ID', ns).text:
                    st.find('cbc:TaxableAmount', ns).text
                for st in doc_tax_total.findall('cac:TaxSubtotal', ns)
            }
            # EXO base must equal the EXO line subtotal, not be deflated by ISC.
            self.assertEqual(taxable_by_scheme['9997'], '83.60')
            # IGV base = 200 + ISC inflation (5.40), then doc-level subtracts
            # the ISC contribution back: 205.40 - 5.40 = 200.00.
            self.assertEqual(taxable_by_scheme['1000'], '200.00')
            # ISC base = original line subtotal, untouched.
            self.assertEqual(taxable_by_scheme['2000'], '200.00')

    def test_invoice_global_discount(self):
        """ Invoice in USD with a global and line nevel discount."""
        with freeze_time(self.frozen_today):
            update_vals_dict = {
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 2000.0,
                        'quantity': 5,
                        'discount': 20.0,
                        'tax_ids': [(6, 0, self.tax_18.ids)],
                    }),
                    Command.create({
                        "name": "Discount",
                        "price_unit": -200.0,
                        "tax_ids": [Command.set(self.tax_18.ids)]
                    }),
                ],
            }
            invoice = self._create_invoice_pe(**update_vals_dict)
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)

        with file_open('l10n_pe_edi/tests/test_files/invoice_global_discount.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_down_payment(self):
        """ Invoice with a downpayment on a sale order. Note the downpayment invoice is not different
        than any other invoice which is why we only look at the final invoice XML to make sure all the
        right data is there. """

        if 'sale' not in self.env["ir.module.module"]._installed():
            self.skipTest("Sale module is not installed")

        self.env.user.group_ids |= self.env.ref('sales_team.group_sale_manager')

        with freeze_time(self.frozen_today):
            sale_order = self.env['sale.order'].create({
                'partner_id': self.partner_a.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 2000.0,
                        'product_uom_qty': 5,
                        'tax_ids': [(6, 0, self.tax_18.ids)],
                    })
                ]
            })
            sale_order.action_confirm()

            context = {
                'active_model': 'sale.order',
                'active_ids': [sale_order.id],
                'active_id': sale_order.id,
                'default_journal_id': self.company_data['default_journal_sale'].id,
            }
            downpayment_1 = self.env['sale.advance.payment.inv'].with_context(context).create({
                'advance_payment_method': 'fixed',
                'fixed_amount': 115,
            })._create_invoices(sale_order)

            downpayment_2 = self.env['sale.advance.payment.inv'].with_context(context).create({
                'advance_payment_method': 'fixed',
                'fixed_amount': 115,
            })._create_invoices(sale_order)

            final = self.env['sale.advance.payment.inv'].with_context(context).create({})._create_invoices(sale_order)

            downpayment_1.action_post()
            downpayment_2.action_post()
            final.action_post()

        edi_xml, _errors = final._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)
        with file_open('l10n_pe_edi/tests/test_files/invoice_final_downpayment.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_down_payment_foreign_currency(self):
        """ Invoice with a downpayment on a sale order. Note the downpayment invoice is not different
        than any other invoice which is why we only look at the final invoice XML to make sure all the
        right data is there. """

        self.ensure_installed('sale')
        self.env.user.group_ids += self.env.ref('sales_team.group_sale_salesman')

        pricelist = self.env['product.pricelist'].create({
            'name': 'Test Pricelist',
            'currency_id': self.other_currency.id,
        })

        with freeze_time(self.frozen_today):
            sale_order = self.env['sale.order'].create({
                'partner_id': self.partner_a.id,
                'pricelist_id': pricelist.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 2000.0,
                        'product_uom_qty': 5,
                        'tax_ids': [(6, 0, self.tax_18.ids)],
                    }),
                ],
            })
            sale_order.action_confirm()

            context = {
                'active_model': 'sale.order',
                'active_ids': [sale_order.id],
                'active_id': sale_order.id,
                'default_journal_id': self.company_data['default_journal_sale'].id,
            }
            downpayment = self.env['sale.advance.payment.inv'].with_context(context).create({
                'advance_payment_method': 'fixed',
                'fixed_amount': 115,
            })._create_invoices(sale_order)

            final = self.env['sale.advance.payment.inv'].with_context(context).create({})._create_invoices(sale_order)

            downpayment.action_post()
            final.action_post()

        edi_xml, _errors = final._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)
        with file_open('l10n_pe_edi/tests/test_files/invoice_final_downpayment_foreign_currency.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_down_payment_with_withholding_tax(self):
        """
        Test the UBL XML of a final invoice generated from a sale order with two fixed-amount
        down payments and a withholding tax applied on the order line.

        Withholding tax totals must be excluded from the XML.
        """

        if 'sale' not in self.env["ir.module.module"]._installed():
            self.skipTest("Sale module is not installed")
        self.env.user.group_ids |= self.env.ref('sales_team.group_sale_manager')

        self.tax_18.include_base_amount = True
        tax_withholding = self.env['account.tax'].create({
            'name': 'tax_withholding',
            'amount_type': 'percent',
            'amount': -3.0,
            'type_tax_use': 'sale',
            'tax_group_id': self.env['account.chart.template'].ref('tax_group_igv_withholding').id,
        })

        with freeze_time(self.frozen_today):
            sale_order = self.env['sale.order'].create({  # noqa: OLS03001
                'partner_id': self.partner_a.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 1000.0,
                        'product_uom_qty': 5,
                        'tax_ids': [Command.set([self.tax_18.id, tax_withholding.id])],
                    })
                ]
            })
            sale_order.action_confirm()

            context = {
                'active_model': 'sale.order',
                'active_ids': [sale_order.id],
                'active_id': sale_order.id,
                'default_journal_id': self.company_data['default_journal_sale'].id,
            }
            downpayment_1 = self.env['sale.advance.payment.inv'].with_context(context).create({  # noqa: OLS03001
                'advance_payment_method': 'fixed',
                'fixed_amount': 115,
            })._create_invoices(sale_order)
            downpayment_1.action_post()

            downpayment_to_reverse = self.env['sale.advance.payment.inv'].with_context(context).create({  # noqa: OLS03001
                'advance_payment_method': 'fixed',
                'fixed_amount': 115,
            })._create_invoices(sale_order)
            downpayment_to_reverse.action_post()

            reversal_wizard = self.env['account.move.reversal'].with_context(
                active_model="account.move",
                active_ids=downpayment_to_reverse.ids
            ).create({
                'reason': 'Test reason',
                'journal_id': downpayment_to_reverse.journal_id.id,
                'l10n_pe_edi_refund_reason': '01',
            })
            action = reversal_wizard.modify_moves()
            downpayment_2 = self.env['account.move'].browse(action['res_id'])
            downpayment_2.action_post()

            final = self.env['sale.advance.payment.inv'].with_context(context).create({})._create_invoices(sale_order)  # noqa: OLS03001
            final.action_post()

        edi_xml, _errors = final._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)
        with file_open('l10n_pe_edi/tests/test_files/invoice_final_downpayment_withhold.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_withholding(self):
        """ Invoice with withholding tax associated. There should be only one allowance node
            even though there are two lines with the withholding tax. """
        self.tax_18.include_base_amount = True
        tax_withholding = self.env['account.tax'].create({
            'name': 'tax_withholding',
            'amount_type': 'percent',
            'amount': -3.0,
            'type_tax_use': 'sale',
            'tax_group_id': self.env['account.chart.template'].ref('tax_group_igv_withholding').id,
        })

        with freeze_time(self.frozen_today):
            update_vals_dict = {
                'invoice_line_ids': [
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 0.481936,
                        'quantity': 300,
                        'tax_ids': [(6, 0, [tax_withholding.id, self.tax_18.id])],
                    }),
                    Command.create({
                        'product_id': self.product.id,
                        'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                        'price_unit': 0.747376,
                        'quantity': 300,
                        'tax_ids': [(6, 0, [tax_withholding.id, self.tax_18.id])],
                    }),
                ],
            }
            invoice = self._create_invoice_pe(**update_vals_dict)
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)
        with file_open('l10n_pe_edi/tests/test_files/invoice_withholding.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_icbper_fixed_tax(self):
        """ Test that an invoice with an ICBPER fixed-amount tax generates EDI XML without errors."""
        tax_icbper = self.env['account.tax'].create({
            'name': 'ICBPER',
            'amount_type': 'fixed',
            'amount': 0.5,
            'l10n_pe_edi_tax_code': '7152',
            'l10n_pe_edi_unece_category': 'S',
            'type_tax_use': 'sale',
            'tax_group_id': self.env['account.chart.template'].ref('tax_group_icbper').id,
        })
        with freeze_time(self.frozen_today):
            move = self._create_invoice(
                invoice_line_ids=[Command.create({
                    'product_id': self.product.id,
                    'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                    'price_unit': 2000.0,
                    'quantity': 5,
                    'tax_ids': [Command.set([tax_icbper.id])],
                })],
            )
            move.action_post()

            generated_files, _errors = move._l10n_pe_edi_generate_invoice_bstr()
            self.assertTrue(generated_files)

    def test_invoice_foreign_customer(self):
        """Invoice for a foreign customer"""
        self.partner_a.write({
            "country_id": self.env.ref('base.co').id,
            "vat": "213123432-1",  # a Colombian NIT, the partner is no longer identified in Peru
        })
        with freeze_time(self.frozen_today):
            invoice = self._create_invoice_pe(
                l10n_latam_document_type_id=self.env.ref('l10n_pe.document_type02').id,
                invoice_payment_term_id=self.env.ref("account.account_payment_term_end_following_month").id,
                l10n_pe_edi_operation_type='0200',
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product.id,
                        'price_unit': 990.0,
                        'quantity': 1,
                        'tax_ids': [Command.set(self.tax_18.ids)],
                    }),
                ],
            )
            invoice.action_post()

        edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()
        current_etree = self.get_xml_tree_from_string(edi_xml)
        with file_open('l10n_pe_edi/tests/test_files/foreign_customer.xml', 'rb') as expected_file:
            expected_etree = self.get_xml_tree_from_string(expected_file.read())
        self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_payment_term_ordering(self):
        """ Instalments (Cuota001/002/003) must be emitted in ascending due-date order.

        When a 3-instalment payment term is used (e.g. 50 % / 30 % / 20 %), the
        resulting cac:PaymentTerms nodes must be sorted by PaymentDueDate, not
        by database row insertion order.  Regression for bug where the amounts
        were mixed up between cuotas.
        """
        payment_term = self.env['account.payment.term'].create({
            'name': '20/30/50 instalment',
            # Lines intentionally created in descending nb_days order so that without the
            # date_maturity sort fix, the DB insertion order would assign Cuota001 to the
            # latest/largest instalment instead of the earliest/smallest one.
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 15}),
                Command.create({'value': 'percent', 'value_amount': 30, 'nb_days': 10}),
                Command.create({'value': 'percent', 'value_amount': 20, 'nb_days': 5}),
            ],
        })

        with freeze_time(self.frozen_today):
            invoice = self.env['account.move'].create({
                'name': 'F FFI-%s1' % self.time_name,
                'move_type': 'out_invoice',
                'partner_id': self.partner_a.id,
                'invoice_date': '2017-01-01',
                'date': '2017-01-01',
                'invoice_payment_term_id': payment_term.id,
                'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
                'invoice_line_ids': [Command.create({
                    'product_id': self.product.id,
                    'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                    'price_unit': 530.0,
                    'quantity': 1,
                    'tax_ids': [Command.set(self.tax_18.ids)],
                })],
            })
            invoice.action_post()

            edi_xml, _errors = invoice._l10n_pe_edi_generate_invoice_bstr()

        invoice_etree = self.get_xml_tree_from_string(edi_xml)

        # Extract only the Cuota instalment nodes (skip the summary FormaPago/Credito node)
        cuota_nodes = [
            node for node in invoice_etree.findall('.//{*}PaymentTerms')
            if (node.findtext('{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PaymentMeansID') or '').startswith('Cuota')
        ]

        # Wrap extracted nodes in a root element so we can use assertXmlTreeEqual
        generated_root = etree.Element('root')
        for node in cuota_nodes:
            generated_root.append(node)

        expected_root = self.get_xml_tree_from_string(b'''<root
                xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
            <cac:PaymentTerms>
                <cbc:ID>FormaPago</cbc:ID>
                <cbc:PaymentMeansID>Cuota001</cbc:PaymentMeansID>
                <cbc:Amount currencyID="PEN">125.08</cbc:Amount>
                <cbc:PaymentDueDate>2017-01-06</cbc:PaymentDueDate>
            </cac:PaymentTerms>
            <cac:PaymentTerms>
                <cbc:ID>FormaPago</cbc:ID>
                <cbc:PaymentMeansID>Cuota002</cbc:PaymentMeansID>
                <cbc:Amount currencyID="PEN">187.62</cbc:Amount>
                <cbc:PaymentDueDate>2017-01-11</cbc:PaymentDueDate>
            </cac:PaymentTerms>
            <cac:PaymentTerms>
                <cbc:ID>FormaPago</cbc:ID>
                <cbc:PaymentMeansID>Cuota003</cbc:PaymentMeansID>
                <cbc:Amount currencyID="PEN">312.70</cbc:Amount>
                <cbc:PaymentDueDate>2017-01-16</cbc:PaymentDueDate>
            </cac:PaymentTerms>
        </root>''')
        self.assertXmlTreeEqual(generated_root, expected_root)

    def test_reversal_cancel_reason_mapping(self):
        """Test that the cancel and credit reason in the reversal wizard are correctly mapped to the fields in the Peruvian EDI tab."""

        move = self._create_invoice_pe()
        move.action_post()

        reversal_wizard = self.env['account.move.reversal'].with_context(
            active_model="account.move",
            active_ids=move.ids
        ).create({
            'reason': 'Test reason',
            'journal_id': move.journal_id.id,
            'l10n_pe_edi_refund_reason': '01',
        })
        action = reversal_wizard.reverse_moves()
        reverse_move = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(reverse_move.l10n_pe_edi_cancel_reason, 'Test reason')
        self.assertEqual(reverse_move.l10n_pe_edi_refund_reason, '01')

    def test_post_invoice_batch_with_missing_taxes_returns_error(self):
        """Sending multiple invoices with missing taxes must record an error on each move.
        """
        invoice1 = self._create_invoice_pe(
            invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'price_unit': 1000.0,
                'quantity': 1,
                'tax_ids': [],
            })],
        )
        invoice2 = self._create_invoice_pe(
            invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'price_unit': 500.0,
                'quantity': 1,
                'tax_ids': [],
            })],
        )
        (invoice1 | invoice2).action_post()

        self.env['account.move.send']._generate_and_send_invoices(invoice1 + invoice2, allow_raising=False)
        self.assertTrue(invoice1.l10n_pe_edi_warnings, "invoice1 should have EDI warnings recorded")
        self.assertTrue(invoice2.l10n_pe_edi_warnings, "invoice2 should have EDI warnings recorded")

    def test_invoice_downpayment_rounding(self):
        """ Test a 40% down payment invoice on a sale order with several 0% taxes and
            products having price unit with more than 2 decimals.
        """
        self.ensure_installed('sale')

        self.env.user.group_ids |= self.env.ref('sales_team.group_sale_manager')
        self.env.company.tax_calculation_rounding_method = 'round_globally'

        tax_group_exo = self.env['account.tax.group'].create({
            'name': 'EXO',
            'l10n_pe_edi_code': 'EXO',
        })
        tax_group_ina = self.env['account.tax.group'].create({
            'name': 'INA',
            'l10n_pe_edi_code': 'INA',
        })
        tax_0_ina = self.env['account.tax'].create({
            'name': 'tax_0_ina',
            'amount_type': 'percent',
            'amount': 0,
            'l10n_pe_edi_tax_code': '9998',
            'l10n_pe_edi_unece_category': 'Z',
            'type_tax_use': 'sale',
            'tax_group_id': tax_group_ina.id,
        })
        tax_0_exo = self.env['account.tax'].create({
            'name': 'tax_0_exo',
            'amount_type': 'percent',
            'amount': 0,
            'l10n_pe_edi_tax_code': '9997',
            'l10n_pe_edi_unece_category': 'Z',
            'type_tax_use': 'sale',
            'tax_group_id': tax_group_exo.id,
        })
        product_a = self.env['product.product'].create({
            'name': 'product_pe_a',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'unspsc_code_id': self.env.ref('product_unspsc.unspsc_code_01010101').id,
        })
        product_b = self.env['product.product'].create({
            'name': 'product_pe_b',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'unspsc_code_id': self.env.ref('product_unspsc.unspsc_code_01010101').id,
        })
        product_c = self.env['product.product'].create({
            'name': 'product_pe_c',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'unspsc_code_id': self.env.ref('product_unspsc.unspsc_code_01010101').id,
        })

        with freeze_time(self.frozen_today):
            sale_order = self.env['sale.order'].create({  # noqa: OLS03001
                'partner_id': self.partner_a.id,
                'order_line': [
                    Command.create({
                        'product_id': product_a.id,
                        'price_unit': 123.50,
                        'product_uom_qty': 3,
                        'tax_ids': [Command.set(self.tax_18.ids)],
                    }),
                    Command.create({
                        'product_id': product_b.id,
                        'price_unit': 27.544216,
                        'product_uom_qty': 2,
                        'tax_ids': [Command.set(tax_0_ina.ids)],
                    }),
                    Command.create({
                        'product_id': product_c.id,
                        'price_unit': 43.490867,
                        'product_uom_qty': 1,
                        'tax_ids': [Command.set(tax_0_exo.ids)],
                    }),
                ]
            })
            sale_order.action_confirm()

            context = {
                'active_model': 'sale.order',
                'active_ids': [sale_order.id],
                'active_id': sale_order.id,
                'default_journal_id': self.company_data['default_journal_sale'].id,
            }
            downpayment = self.env['sale.advance.payment.inv'].with_context(context).create({  # noqa: OLS03001
                'advance_payment_method': 'percentage',
                'amount': 40,
            })._create_invoices(sale_order)
            downpayment.action_post()

            edi_xml, _errors = downpayment._l10n_pe_edi_generate_invoice_bstr()
            current_etree = self.get_xml_tree_from_string(edi_xml)
            with file_open('l10n_pe_edi/tests/test_files/invoice_downpayment_rounding.xml', 'rb') as expected_file:
                expected_etree = self.get_xml_tree_from_string(expected_file.read())
            self.assertXmlTreeEqual(current_etree, expected_etree)

    def test_invoice_cash_rounding(self):
        """ The cash rounding amount must be included in the PayableAmount. """
        cash_rounding = self.env['account.cash.rounding'].create({
            'name': 'Round down to 0.10',
            'rounding': 0.10,
            'strategy': 'add_invoice_line',
            'rounding_method': 'DOWN',
            'profit_account_id': self.company_data['default_account_revenue'].id,
            'loss_account_id': self.company_data['default_account_expense'].id,
        })
        move = self._create_invoice(
            currency_id=self.env.company.currency_id.id,
            invoice_cash_rounding_id=cash_rounding.id,
            invoice_line_ids=[(0, 0, {
                'product_id': self.product.id,
                'price_unit': 12.50,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })],
        )
        move.action_post()

        xml, _errors = self.env['account.edi.xml.ubl_pe']._export_invoice(move)
        monetary_total = self.get_xml_tree_from_string(xml).find('.//{*}LegalMonetaryTotal')
        self.assertEqual(monetary_total.findtext('{*}TaxInclusiveAmount'), '14.75')
        self.assertEqual(monetary_total.findtext('{*}PayableRoundingAmount'), '-0.05')
        self.assertEqual(monetary_total.findtext('{*}PayableAmount'), '14.70')
