from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_mx_edi.tests.common_sat_download import (
    TestCfdiRequestCommon,
    DEFAULT_CFDI_UUID,
)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCfdiDocumentImport(TestCfdiRequestCommon):

    def _create_documents_from_data(self, cfdi_data, cfdi_request=None):
        cfdi_request = cfdi_request or self._create_new_request(state='unpacking')
        return self.env['l10n_mx_edi.document']._create_documents_from_cfdi_files(
            [sample['raw_bytes'] for sample in self._create_cfdi_samples(cfdi_data)], cfdi_request,
        )

    @mute_logger('odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document')
    def test_import_creates_invoices(self):
        """Only income (I) and egress (E) CFDIs become invoices."""
        cfdi_data = [
            ('E01FA6FF-D5E9-47E0-AC2F-41922B51E1FB', 'I'),
            ('A3CAF74F-0D92-4708-9761-33EA2ED082B5', 'E'),
            ('FA6FA55D-B466-4728-85FD-D44C40DD2279', 'P'),
        ]
        documents = self._create_documents_from_data(cfdi_data)
        self.assertEqual(set(documents.mapped('state')), {'to_import'})
        self._trigger_cron(self.import_cron)

        by_uuid = {d.attachment_uuid: d for d in documents}
        self.assertRecordValues(documents, [
            {'state': 'invoice_sent', 'sat_state': 'not_defined', 'receipt_type': 'I', 'attachment_uuid': 'E01FA6FF-D5E9-47E0-AC2F-41922B51E1FB'},
            {'state': 'invoice_sent', 'sat_state': 'not_defined', 'receipt_type': 'E', 'attachment_uuid': 'A3CAF74F-0D92-4708-9761-33EA2ED082B5'},
            {'state': 'to_import_error', 'sat_state': 'not_defined', 'receipt_type': 'P', 'attachment_uuid': 'FA6FA55D-B466-4728-85FD-D44C40DD2279'},
        ])
        # Exactly the two registered receipt types produced invoices, and each is the document's own.
        invoices = self.env['account.move'].search([('l10n_mx_edi_cfdi_uuid', 'in', list(by_uuid))])
        self.assertEqual(len(invoices), 2)
        self.assertEqual(documents.move_id, invoices)
        self.assertEqual(invoices.l10n_mx_edi_cfdi_attachment_id, documents.move_id.mapped('l10n_mx_edi_invoice_document_ids.attachment_id'))

    def test_import_skips_already_staged_documents(self):
        """Staging CFDIs that already have a document does not create duplicates."""
        cfdi_data = [
            ('E01FA6FF-D5E9-47E0-AC2F-41922B51E1FB', 'I'),
            ('A3CAF74F-0D92-4708-9761-33EA2ED082B5', 'I'),
        ]
        first = self._create_documents_from_data(cfdi_data)
        self.assertEqual(len(first), 2)

        # Staging the same CFDIs again yields no new documents.
        second = self._create_documents_from_data(cfdi_data)
        self.assertFalse(second)

    @mute_logger('odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document')
    def test_import_without_journal_marks_error(self):
        """A missing journal marks the document as errored instead of crashing the cron."""
        document = self._create_documents_from_data([(DEFAULT_CFDI_UUID, 'I')])
        sale_domain = [*self.env['account.journal']._check_company_domain(document.company_id),
            ('type', '=', 'sale')]
        self.env['account.journal'].search(sale_domain).unlink()
        self.assertFalse(self.env['account.journal'].search_count(sale_domain, limit=1), 'No sale journal should exist.')

        self._trigger_cron(self.import_cron)
        self.assertRecordValues(document, [
            {
                'state': 'to_import_error',
                'sat_state': 'not_defined',
                'message': 'Import of document failed with: No journal could be found in '
                           'company ESCUELA KEMPER URGATE for any of those types: sale',
            },
        ])

    def test_received_cfdi_becomes_vendor_bill(self):
        """A received CFDI (issued by a third party to the company) becomes a vendor bill."""
        company_rfc = self.company_data['company'].partner_id.commercial_partner_id.vat
        supplier_rfc = self.partner_mx.vat
        self.assertNotEqual(company_rfc, supplier_rfc)
        cfdi_samples = self._create_cfdi_samples(
            [(DEFAULT_CFDI_UUID, 'I')], emisor_rfc=supplier_rfc, receptor_rfc=company_rfc,
        )
        self.env['l10n_mx_edi.document']._create_documents_from_cfdi_files(
            [sample['raw_bytes'] for sample in cfdi_samples], self._create_new_request(state='unpacking'),
        )
        self._trigger_cron(self.import_cron)

        invoice = self.env['account.move'].search([('l10n_mx_edi_cfdi_uuid', '=', DEFAULT_CFDI_UUID)])
        self.assertEqual(invoice.move_type, 'in_invoice')

    def test_same_uuid_twice_yields_one_document(self):
        """The same UUID appearing twice in one package yields a single document."""
        documents = self._create_documents_from_data([
            (DEFAULT_CFDI_UUID, 'I'),
            (DEFAULT_CFDI_UUID, 'I'),
        ])
        self.assertEqual(len(documents), 1)

    def test_no_cfdi_file_skipped(self):
        cfdi_sample = self._create_cfdi_samples([(DEFAULT_CFDI_UUID, 'I')])[0]['raw_bytes']
        documents = self.env['l10n_mx_edi.document']._create_documents_from_cfdi_files(
            [b'not-a-cfdi-file', cfdi_sample], self._create_new_request(state='unpacking'),
        )
        self.assertEqual(documents.mapped('attachment_uuid'), [DEFAULT_CFDI_UUID])
