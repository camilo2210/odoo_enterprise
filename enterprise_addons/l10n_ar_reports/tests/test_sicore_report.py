# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.addons.l10n_ar_withholding.tests.test_withholding_ar_ri import TestArWithholdingArRi
from odoo.tests import tagged
from odoo.tools import file_open


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSicoreReport(TestArWithholdingArRi, TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('l10n_ar_reports.l10n_ar_sicore_report')
        cls.options = cls._generate_options(cls.report, fields.Date.from_string('2023-01-01'), fields.Date.from_string('2023-01-31'))

    def _create_invoice_and_set_withholding_sequence(self, tax, price_unit=30000.0):
        """Create an invoice and set the withholding sequence for the tax."""
        tax.withholding_sequence_id = self.earnings_withholding_sequence
        return self.create_invoice(product_id=self.service_iva_21, price_unit=price_unit, tax_ids=None)

    def _create_partner_tax_and_register_payment(self, invoice, tax, create_payments=True):
        self.env['l10n_ar.partner.tax'].create({
            'partner_id': self.res_partner_adhoc.id,
            'company_id': invoice.company_id.id,
            'tax_id': tax.id
        })
        wizard = self.create_payment_register(invoice, {tax: invoice.amount_untaxed})
        if create_payments:
            wizard.action_create_payments()
        return wizard

    def _test_sicore_txt_file(self, filename):
        out_txt = self.env['l10n_ar.sicore.report.handler']._sicore_book_get_txt_files(self.options).decode('ISO-8859-1')
        res_file = file_open('l10n_ar_reports/tests/' + filename, 'rb').read().decode('ISO-8859-1')
        self.assertEqual(out_txt, res_file)

    def test_01_earnings_withholding_applied_with_scale_sicore_txt(self):
        """Two payments with same withholding tax (with tax type 'Earnings Scale'). Verify SICORE txt."""
        tax = self.tax_wth_purchase_earnings_scale
        invoice = self._create_invoice_and_set_withholding_sequence(tax=tax)
        self._create_partner_tax_and_register_payment(invoice, tax)
        invoice2 = self._create_invoice_and_set_withholding_sequence(tax=tax, price_unit=40000.0)
        self._create_partner_tax_and_register_payment(invoice2, tax)
        self._test_sicore_txt_file('test_01_earnings_withholding_applied_with_scale_sicore_txt.txt')

    def test_02_earnings_withholding_applied_sicore_txt(self):
        """Two payments with same withholding tax (with tax type 'Earnings'). Verify SICORE txt."""
        tax = self.tax_wth_purchase_earnings
        invoice = self._create_invoice_and_set_withholding_sequence(tax=tax)
        self._create_partner_tax_and_register_payment(invoice, tax)
        invoice2 = self._create_invoice_and_set_withholding_sequence(tax=tax, price_unit=40000.0)
        self._create_partner_tax_and_register_payment(invoice2, tax)
        self._test_sicore_txt_file('test_02_earnings_withholding_applied_sicore_txt.txt')

    def test_03_earnings_partial_payment_withholding_applied_with_scale_sicore_txt(self):
        """Partial payment with withholding tax (with tax type 'Earnings Scale'). Verify SICORE txt."""
        tax = self.tax_wth_purchase_earnings_scale
        invoice = self._create_invoice_and_set_withholding_sequence(tax=tax)
        wizard = self._create_partner_tax_and_register_payment(invoice, tax, create_payments=False)
        wizard.amount -= 2420
        wizard.action_create_payments()
        self._test_sicore_txt_file('test_03_earnings_partial_payment_withholding_applied_with_scale_sicore_txt.txt')
