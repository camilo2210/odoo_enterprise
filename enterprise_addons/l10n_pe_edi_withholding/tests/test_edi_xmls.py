# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.l10n_pe_edi_withholding.tests.common import TestPeEdiWithholdingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEdiXmls(TestPeEdiWithholdingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        with file_open('l10n_pe_edi_withholding/tests/test_files/retention_basic.xml', 'rb') as f:
            cls.expected_retention_basic = f.read()

        with file_open('l10n_pe_edi_withholding/tests/test_files/retention_foreign_currency.xml', 'rb') as f:
            cls.expected_retention_foreign_currency = f.read()

        with file_open('l10n_pe_edi_withholding/tests/test_files/retention_exchange_rate_change.xml', 'rb') as f:
            cls.expected_retention_exchange_rate_change = f.read()

        with file_open('l10n_pe_edi_withholding/tests/test_files/retention_pen_bill_usd_payment.xml', 'rb') as f:
            cls.expected_retention_pen_bill_usd_payment = f.read()

        with file_open('l10n_pe_edi_withholding/tests/test_files/retention_multi_bill.xml', 'rb') as f:
            cls.expected_retention_multi_bill = f.read()

        with file_open('l10n_pe_edi_withholding/tests/test_files/retention_partial_payment.xml', 'rb') as f:
            cls.expected_retention_partial_payment = f.read()

    # -------------------------------------------------------------------------
    # XML generation tests
    # -------------------------------------------------------------------------

    def test_retention_basic(self):
        """Single vendor bill in PEN, 3% withholding - no exchange rate node."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()
            payment.withholding_line_ids[:1].name = 'RRR1-00000001'
            xml_bytes = payment._l10n_pe_edi_generate_retention_bstr()

        current = self.get_xml_tree_from_string(xml_bytes)
        expected = self.get_xml_tree_from_string(self.expected_retention_basic)
        self.assertXmlTreeEqual(current, expected)

    def test_retention_foreign_currency(self):
        """Bill in USD, payment in PEN - exchange rate node present."""
        with freeze_time(self.frozen_today):
            bill = self._create_vendor_bill(currency_id=self.other_currency.id)
            payment = self._create_payment_with_retention(bills=bill)
            payment.withholding_line_ids[:1].name = 'RRR1-00000001'
            xml_bytes = payment._l10n_pe_edi_generate_retention_bstr()

        current = self.get_xml_tree_from_string(xml_bytes)
        expected = self.get_xml_tree_from_string(self.expected_retention_foreign_currency)
        self.assertXmlTreeEqual(current, expected)

    def test_retention_exchange_rate_change(self):
        """Bill in USD on 2017-01-01 (0.5 PEN/USD), payment on 2017-02-01 (0.25 PEN/USD).

        Shows what the retention XML emits when the exchange rate moves between
        the bill date and the payment date: all PEN amounts (retention, net paid,
        bill conversion) are computed at the payment date rate, halving the
        retention in PEN compared to the bill date rate.
        """
        self.env['res.currency.rate'].create({
            'name': '2017-01-15',
            'rate': 4.0,
            'currency_id': self.other_currency.id,
            'company_id': self.company_data['company'].id,
        })

        with freeze_time(self.frozen_today):
            bill = self._create_vendor_bill(currency_id=self.other_currency.id)

        with freeze_time('2017-02-01'):
            payment = self._create_payment_with_retention(bills=bill)
            payment.withholding_line_ids[:1].name = 'RRR1-00000001'
            xml_bytes = payment._l10n_pe_edi_generate_retention_bstr()

        current = self.get_xml_tree_from_string(xml_bytes)
        expected = self.get_xml_tree_from_string(self.expected_retention_exchange_rate_change)
        self.assertXmlTreeEqual(current, expected)

    def test_retention_pen_bill_usd_payment(self):
        """Bill in PEN (company currency), payment in USD on 2017-02-01.

        Shows what the retention XML emits when the bill is denominated in
        the company currency but the vendor is paid in a foreign currency,
        and the exchange rate has changed between the bill and the payment.
        """
        self.env['res.currency.rate'].create({
            'name': '2017-01-15',
            'rate': 4.0,
            'currency_id': self.other_currency.id,
            'company_id': self.company_data['company'].id,
        })

        with freeze_time(self.frozen_today):
            bill = self._create_vendor_bill()

        with freeze_time('2017-02-01'):
            payment = self._create_payment_with_retention(bills=bill, payment_currency=self.other_currency)
            payment.withholding_line_ids[:1].name = 'RRR1-00000001'
            xml_bytes = payment._l10n_pe_edi_generate_retention_bstr()

        current = self.get_xml_tree_from_string(xml_bytes)
        expected = self.get_xml_tree_from_string(self.expected_retention_pen_bill_usd_payment)
        self.assertXmlTreeEqual(current, expected)

    def test_retention_partial_payment(self):
        """Partial payment reconciles half a bill - withholding is prorated, not applied on full."""
        with freeze_time(self.frozen_today):
            bill = self._create_vendor_bill()
            payment = self._create_payment_with_retention(bills=bill, payment_amount=5900.0)
            payment.withholding_line_ids[:1].name = 'RRR1-00000001'
            xml_bytes = payment._l10n_pe_edi_generate_retention_bstr()

        current = self.get_xml_tree_from_string(xml_bytes)
        expected = self.get_xml_tree_from_string(self.expected_retention_partial_payment)
        self.assertXmlTreeEqual(current, expected)

    def test_retention_multi_bill(self):
        """Two bills reconciled with one payment - proportional retention distribution."""
        with freeze_time(self.frozen_today):
            bill_1 = self._create_vendor_bill(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'price_unit': 5000.0,
                'quantity': 1,
                'tax_ids': [Command.set((self.purchase_tax_18 | self.withholding_tax).ids)],
            })])
            bill_2 = self._create_vendor_bill(invoice_line_ids=[Command.create({
                'product_id': self.product.id,
                'price_unit': 3000.0,
                'quantity': 1,
                'tax_ids': [Command.set((self.purchase_tax_18 | self.withholding_tax).ids)],
            })])
            payment = self._create_payment_with_retention(bills=bill_1 | bill_2)
            payment.withholding_line_ids[:1].name = 'RRR1-00000001'
            xml_bytes = payment._l10n_pe_edi_generate_retention_bstr()

        current = self.get_xml_tree_from_string(xml_bytes)
        expected = self.get_xml_tree_from_string(self.expected_retention_multi_bill)
        self.assertXmlTreeEqual(current, expected)

    # -------------------------------------------------------------------------
    # Non-XML tests
    # -------------------------------------------------------------------------

    def test_is_required_compute(self):
        """l10n_pe_edi_is_required depends on state, withholding, and PE country."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()
        self.assertTrue(payment.l10n_pe_edi_is_required)

    def test_retention_number_mirrors_line(self):
        """Retention number is computed from the (single) withholding line's name."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        self.assertEqual(payment.l10n_pe_edi_retention_number, payment.withholding_line_ids[:1].name)

    def test_retention_filename(self):
        """Filename follows the pattern: {VAT}-20-{retention_number}."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        payment.withholding_line_ids[:1].name = 'RRR1-00000001'
        expected_filename = f'{payment.company_id.vat}-20-RRR1-00000001'
        self.assertEqual(payment._l10n_pe_edi_generate_retention_filename(), expected_filename)

    def test_send_no_reconciled_bills(self):
        """Send without reconciled bills sets warning and stays to_send."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        # remove_move_reconcile does not invalidate reconciled_bill_ids on its own.
        payment.move_id.line_ids.remove_move_reconcile()
        payment.invalidate_recordset(['reconciled_bill_ids'])

        payment.action_l10n_pe_edi_send_retention()

        self.assertEqual(payment.l10n_pe_edi_status, 'to_send')
        self.assertTrue(payment.l10n_pe_edi_warnings)

    def test_send_success_sets_status(self):
        """Successful send sets status to 'sent' and clears warnings."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        with patch.object(self.env.registry['account.payment'], '_l10n_pe_edi_post_retention', return_value={'success': True, 'zip_document': b'fake'}):
            payment.action_l10n_pe_edi_send_retention()

        self.assertEqual(payment.l10n_pe_edi_status, 'sent')
        self.assertFalse(payment.l10n_pe_edi_warnings)
        self.assertTrue(payment.l10n_pe_edi_retention_number)

    def test_send_error_preserves_to_send(self):
        """Failed send keeps status as to_send with error warnings."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        with patch.object(self.env.registry['account.payment'], '_l10n_pe_edi_post_retention', return_value={'message': 'Connection timeout'}):
            payment.action_l10n_pe_edi_send_retention()

        self.assertEqual(payment.l10n_pe_edi_status, 'to_send')
        self.assertTrue(payment.l10n_pe_edi_warnings)
        self.assertIn('Connection timeout', payment.l10n_pe_edi_warnings['edi_error']['message'])

    def test_withholding_line_name_pe(self):
        """PE withholding lines are named via the tax's withholding_sequence_id."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        for line in payment.withholding_line_ids:
            self.assertTrue(line.name)
            self.assertEqual(line.tax_id.withholding_sequence_id, self.withholding_sequence)

    def test_credential_methods(self):
        """Credential methods return correct test environment URLs."""
        with freeze_time(self.frozen_today):
            payment = self._create_payment_with_retention()

        company = payment.company_id
        retention_wsdl = payment._l10n_pe_edi_get_retention_sunat_wsdl()
        self.assertIn('otroscpe-gem-beta', retention_wsdl)

        # Estela credentials (test env): WSDL is provider-specific, not the SUNAT one.
        company.l10n_pe_edi_provider = 'digiflow'
        estela_creds = company._l10n_pe_edi_get_credentials(sunat_wsdl=retention_wsdl)
        self.assertEqual(estela_creds['fault_ns'], 's')
        self.assertIn('ose-test.com', estela_creds['wsdl'])

        # SUNAT credentials (test env): the retention WSDL is used as-is.
        company.l10n_pe_edi_provider = 'sunat'
        sunat_creds = company._l10n_pe_edi_get_credentials(sunat_wsdl=retention_wsdl)
        self.assertEqual(sunat_creds['fault_ns'], 'soap-env')
        self.assertEqual(sunat_creds['wsdl'], retention_wsdl)
