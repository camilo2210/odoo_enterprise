from unittest.mock import patch

from odoo.addons.l10n_be_codabox.tests.common import TestCodaboxCommon
from odoo.tests import tagged, RecordCapturer


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDocumentsCodabox(TestCodaboxCommon):

    _test_user_groups = None  # FIXME list needed groups

    @patch('odoo.addons.l10n_be_codabox.models.account_journal.AccountJournal._l10n_be_codabox_fetch_transactions_from_iap')
    def test_codabox_file_import_document_creation(self, patched_l10n_be_codabox_fetch_transactions_from_iap):
        """Check that bank statement attachments are synchronized with documents using codabox."""
        FolderSetting = self.env['documents.account.folder.setting']
        patched_l10n_be_codabox_fetch_transactions_from_iap.return_value = [(self.coda_file_b64, '')]
        self.env.company.l10n_be_codabox_is_connected = True
        with RecordCapturer(self.env['account.bank.statement']) as bank_stmt_capturer:
            self.env['account.journal']._l10n_be_codabox_fetch_coda_transactions(self.env.company)
        imported_statement = bank_stmt_capturer.records
        self.assertEqual(len(imported_statement), 1)
        self.assertFalse(imported_statement.message_main_attachment_id)
        statement_attachments = self.env['ir.attachment'].search(
            [('res_model', '=', imported_statement._name), ('res_id', '=', imported_statement.id)])
        self.assertEqual(len(statement_attachments), 2)
        self.assertTrue(FolderSetting.search([('journal_id', '=', imported_statement.journal_id.id)]),
                        'Ensure the synchronization is enabled (enabled by default)')
        statement_document = self.env['documents.document'].search([('attachment_id', 'in', statement_attachments.ids)])
        self.assertEqual(len(statement_document), 1)
        self.assertEqual(statement_document.attachment_id.mimetype, 'application/pdf',
                         'Only the pdf is synchronized with document (not the coda file)')
