# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

from odoo.tools import file_open

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

MAX_WAIT_ITER = 6
CODE_98_ERROR_MSG = "The cancellation request has not yet finished processing by SUNAT. Please retry in a few minutes.\n*SOAP status code: *98"


def _get_pe_current_datetime():
    return datetime.now(tz=ZoneInfo('America/Lima'))


class TestPeEdiCommon(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()

        cls.frozen_today = datetime(year=2017, month=1, day=1, hour=0, minute=0, second=0, tzinfo=UTC)

        # Allow to see the full result of AssertionError.
        cls.maxDiff = None

        # Replace USD by the fake currency created in setup (GOL).
        cls.other_currency = cls.setup_other_currency('USD', rounding=0.01)

        # ==== Config ====

        cls.certificate = cls.env['certificate.certificate'].create({
            'name': 'PE test certificate',
            'content': cls.file_read('l10n_pe_edi/demo/certificates/certificate.pfx'),
            'pkcs12_password': '12345678a',
            'company_id': cls.company_data['company'].id,
        })

        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.pe').id,
            'l10n_pe_edi_provider': 'digiflow',
            'l10n_pe_edi_certificate_id': cls.certificate.id,
            'l10n_pe_edi_test_env': True,
        })

        cls.national_bank_account = cls.env['res.partner.bank'].create({
            'account_number': 'CUENTAPRUEBA',
            'bank_bic': 'BANCPEPL',
            'clearing_label_id': cls.env.ref('base.clearing_label_pe').id,
            'clearing_number': 18,
            'partner_id': cls.company_data['company'].partner_id.id,
            'allow_out_payment': True,
        })
        cls.company_data['company'].partner_id.write({
            'vat': "20557912879",
        })

        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True

        iap_service = cls.env.ref('l10n_pe_edi.iap_service_l10n_pe_edi')
        cls.iap_account = cls.env['iap.account'].create({
            'service_id': iap_service.id,
            'company_ids': [(6, 0, cls.company_data['company'].ids)],
        })

        # Prevent the xsd validation because it could lead to a not-deterministic behavior since the xsd is downloaded
        # by a CRON.
        xsd_attachments = cls.env['ir.attachment']
        for doc_type in ('CreditNote', 'DebitNote', 'Invoice'):
            xsd_attachment = cls.env.ref('l10n_pe_edi.UBL-%s-2.1.xsd' % doc_type, raise_if_not_found=False)
            if xsd_attachment:
                xsd_attachments |= xsd_attachment
        if xsd_attachments:
            xsd_attachments.unlink()

        # ==== Business ====

        cls.tax_group = cls.env['account.tax.group'].create({
            'name': "IGV",
            'l10n_pe_edi_code': "IGV",
        })

        cls.tax_18 = cls.env['account.tax'].create({
            'name': 'tax_18',
            'amount_type': 'percent',
            'amount': 18,
            'l10n_pe_edi_tax_code': '1000',
            'l10n_pe_edi_unece_category': 'S',
            'type_tax_use': 'sale',
            'tax_group_id': cls.tax_group.id,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'product_pe',
            'weight': 2,
            'uom_id': cls.env.ref('uom.product_uom_kgm').id,
            'lst_price': 1000.0,
            'property_account_income_id': cls.company_data['default_account_revenue'].id,
            'property_account_expense_id': cls.company_data['default_account_expense'].id,
            'unspsc_code_id': cls.env.ref('product_unspsc.unspsc_code_01010101').id,
        })

        cls.partner_a.write({
            'vat': '20462509236',
            'country_id': cls.env.ref('base.pe').id,
        })

        # Invoice name are tracked by the web-services so this constant tries to get a new unique invoice name at each
        # execution.
        cls.time_name = datetime.now().strftime('%H%M%S')

        # Initialize the cancellation request filename sequence, to avoid collisions between different people running
        # the UTs on the same day
        seq = cls.env.ref('l10n_pe_edi.l10n_pe_edi_summary_sequence')
        if seq.number_next_actual < 50:
            seq.write({'number_next': int(cls.time_name[-3:]) + 60})

        with file_open('l10n_pe_edi/tests/test_files/invoice.xml', 'rb') as expected_invoice_file:
            cls.expected_invoice_xml_values = expected_invoice_file.read()

        with file_open('l10n_pe_edi/tests/test_files/credit_note.xml', 'rb') as expected_credit_note_file:
            cls.expected_refund_xml_values = expected_credit_note_file.read()

        with file_open('l10n_pe_edi/tests/test_files/debit_note.xml', 'rb') as expected_debit_note_file:
            cls.expected_debit_note_xml_values = expected_debit_note_file.read()

    def _create_isc_tax(self, name, isc_type, amount, amount_type='percent'):
        # sequence -1 ensures ISC precedes IGV so include_base_amount cascades.
        return self.env['account.tax'].create({
            'name': name,
            'sequence': -1,
            'amount_type': amount_type,
            'amount': amount,
            'include_base_amount': True,
            'l10n_pe_edi_tax_code': '2000',
            'l10n_pe_edi_unece_category': 'S',
            'l10n_pe_edi_isc_type': isc_type,
            'type_tax_use': 'sale',
            'tax_group_id': self.env['account.chart.template'].ref('tax_group_isc').id,
        })

    def _create_invoice_pe(self, **kwargs):
        vals = {
            'name': 'F FFI-%s1' % self.time_name,
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'date': '2017-01-01',
            'currency_id': self.other_currency.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                'price_unit': 2000.0,
                'quantity': 5,
                'discount': 20.0,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })],
        }
        vals.update(kwargs)
        # Increment the name to make sure it is unique at each call
        self.time_name = str(int(self.time_name) + 1)
        return self.env['account.move'].create(vals)

    def _create_refund(self, **kwargs):
        invoice = self._create_invoice_pe(name='F FFI-%s2' % self.time_name, **kwargs)
        vals = {
            'name': 'F CNE-%s1' % self.time_name,
            'move_type': 'out_refund',
            'ref': 'abc',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'date': '2017-01-01',
            'currency_id': self.other_currency.id,
            'reversed_entry_id': invoice.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type07').id,
            'l10n_pe_edi_refund_reason': '01',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                'price_unit': 1600.0,
                'quantity': 5,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })],
        }
        vals.update(kwargs)
        return self.env['account.move'].create(vals)

    def _create_debit_note(self, **kwargs):
        invoice = self._create_invoice_pe(name='F FFI-%s3' % self.time_name, **kwargs)
        vals = {
            'name': 'F NDI-%s1' % self.time_name,
            'move_type': 'out_invoice',
            'ref': 'abc',
            'partner_id': self.partner_a.id,
            'invoice_date': '2017-01-01',
            'date': '2017-01-01',
            'currency_id': self.other_currency.id,
            'debit_origin_id': invoice.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type08').id,
            'l10n_pe_edi_charge_reason': '01',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                'price_unit': 1600.0,
                'quantity': 5,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })],
        }
        vals.update(kwargs)
        return self.env['account.move'].create(vals)
