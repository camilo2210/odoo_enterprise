from odoo.tests import tagged
from odoo.tests.common import freeze_time
from .common import TestDoEdiCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time('2026-03-23')
class TestEdiPartnerIdentification(TestDoEdiCommon):
    """ Only a partner identified by an RNC may be issued a type 31 document. """

    _test_user_groups = (
        'account.group_account_invoice',
    )

    def test_document_type_automation(self):
        """ Tests that only a partner with an RNC defaults to, and may use, a type 31"""
        for partner, expected_code, available_codes in (
            (self.partner, '31', {'31', '32'}),
            (self.cedula_partner, '32', {'32'}),
            (self.no_vat_partner, '32', {'32'}),
            (self.foreign_partner, '32', {'32'}),
        ):
            with self.subTest(partner=partner.name):
                invoice = self.env['account.move'].create({
                    'move_type': 'out_invoice',
                    'partner_id': partner.id,
                    'journal_id': self.journal_sale.id,
                    'invoice_date': '2026-01-15',
                    'l10n_do_edi_income_type': '01',
                    'invoice_line_ids': [(0, 0, {
                        'product_id': self.product_a.id,
                        'price_unit': 1000.0,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_18.ids)],
                    })],
                    'company_id': self.company.id,
                })
                self.assertEqual(invoice.l10n_latam_document_type_id_code, expected_code)
                self.assertEqual(set(invoice.l10n_latam_available_document_type_ids.mapped('code')), available_codes)

    def test_document_type_31_warning_without_rnc(self):
        """ Tests that a type 31 is blocked for any partner without an RNC"""
        for partner, expect_warning in (
            (self.partner, False),
            (self.cedula_partner, True),
            (self.no_vat_partner, True),
        ):
            with self.subTest(partner=partner.name):
                invoice = self._create_invoice(doc_type=self.doc_type_31, partner_id=partner.id)
                self.assertEqual('missing_partner_vat' in (invoice.l10n_do_edi_warnings or {}), expect_warning)

    def test_document_types_not_31_without_rnc(self):
        """ Tests that a partner without an RNC is not blocked on the other document types"""
        origin_invoice = self._create_invoice(doc_type=self.doc_type_32, partner_id=self.cedula_partner.id)
        origin_invoice.action_post()

        debit_note = self._create_invoice(
            doc_type=self.doc_type_33,
            partner_id=self.cedula_partner.id,
            debit_origin_id=origin_invoice.id,
            l10n_do_edi_modification_code='3',
        )
        credit_note = self._create_invoice(
            doc_type=self.doc_type_34,
            move_type='out_refund',
            partner_id=self.cedula_partner.id,
            reversed_entry_id=origin_invoice.id,
            l10n_do_edi_modification_code='1',
        )
        for invoice in (origin_invoice, debit_note, credit_note):
            with self.subTest(doc_type=invoice.l10n_latam_document_type_id_code):
                self.assertFalse(invoice._l10n_do_edi_blocking_errors())

    def test_reporting_threshold_requires_rnc(self):
        """ Tests that an RNC is required above the reporting threshold, whatever the document type"""
        for partner, expect_warning in (
            (self.partner, False),
            (self.cedula_partner, True),
        ):
            with self.subTest(partner=partner.name):
                invoice = self._create_invoice(
                    doc_type=self.doc_type_32,
                    partner_id=partner.id,
                    invoice_line_ids=[(0, 0, {
                        'product_id': self.product_a.id,
                        'price_unit': 300000.0,
                        'quantity': 1,
                        'tax_ids': [(6, 0, self.tax_18.ids)],
                    })],
                )
                self.assertGreaterEqual(invoice.amount_total_signed, 250000)
                self.assertEqual('missing_partner_vat' in (invoice.l10n_do_edi_warnings or {}), expect_warning)
