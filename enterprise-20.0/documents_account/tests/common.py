from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.documents.tests.test_documents_common import GIF_RAW, PDF_RAW, TEXT_RAW
from odoo.tests import RecordCapturer


class DocumentsAccountHelpersCommon:
    @classmethod
    def setup_sync_journal_folder(cls, journal, folder, company=False):
        """Update or create configuration for journal document synchronization."""
        if setting := cls.env['documents.account.folder.setting'].search(
                [('journal_id', '=', journal.id), ('company_id', '=', company.id if company else cls.env.company.id)]):
            setting.folder_id = folder
            return setting
        setting = cls.env['documents.account.folder.setting'].create({
            'folder_id': folder.id,
            'journal_id': journal.id,
        })
        return setting


class DocumentsAccountTestCommon(AccountTestInvoicingCommon, DocumentsAccountHelpersCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids += cls.quick_ref('documents.group_documents_manager')

        cls.folder_a = cls.env['documents.document'].create({
            'name': 'folder A',
            'type': 'folder',
        })
        cls.folder_a_a = cls.env['documents.document'].create({
            'name': 'folder A - A',
            'folder_id': cls.folder_a.id,
            'type': 'folder',
        })
        cls.document_txt = cls.env['documents.document'].create({
            'raw': TEXT_RAW,
            'name': 'file.txt',
            'mimetype': 'text/plain',
            'folder_id': cls.folder_a_a.id,
        })
        cls.document_gif = cls.env['documents.document'].create({
            'raw': GIF_RAW,
            'name': 'file.gif',
            'mimetype': 'image/gif',
            'folder_id': cls.folder_a.id,
        })
        cls.document_pdf = cls.env['documents.document'].create({
            'raw': PDF_RAW,
            'name': 'file.pdf',
            'mimetype': 'application/pdf',
            'folder_id': cls.folder_a.id,
        })


class DocumentsAccountActionsServerCommon(DocumentsAccountTestCommon):
    """Specialized class for testing Server Actions"""
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.finance_folder = cls.env.ref('documents.document_finance_folder')
        cls.pdf_in_finance_folder = cls.document_pdf.copy()
        cls.pdf_in_finance_folder.folder_id = cls.finance_folder

        cls.journal_type_labels = dict(
            cls.env['account.journal'].fields_get(['type'], ['selection'])['type']['selection']
        )

        target_journals = {
            'sale': 'Sales',
            'purchase': 'Purchases',
            'bank': 'Bank',
            'general': 'Miscellaneous Operations',
            'cash': 'Cash',
            'credit': 'Credit Journal',
        }

        all_journals = cls.env['account.journal'].search(
            cls.env['account.journal']._check_company_domain(cls.env.company)
        )

        cls.journals_by_type = {}
        for j_type, name in target_journals.items():
            journal = all_journals.filtered(lambda j: j.type == j_type and j.name == name)
            if len(journal) != 1:
                raise AssertionError(
                    f"Test setup failed: Expected exactly 1 journal with type='{j_type}' and name='{name}'. "
                    f"Found {len(journal)}."
                )
            cls.journals_by_type[j_type] = journal

        cls.actions_by_type = cls.env['account.journal']._documents_get_embed_on_sync_actions()
        assert cls.actions_by_type

    def _run_action_and_assert_sync(self, action, document, expected_journal):
        """Execute action and assert that the document/record are correctly linked and synced."""
        target_model = 'account.bank.statement' if expected_journal.type == 'bank' else 'account.move'
        with RecordCapturer(self.env[target_model], []) as capture:
            action.with_context(active_model='documents.document', active_id=document.id).run()

        created_record = capture.records
        self.assertEqual(len(created_record), 1)
        self.assertEqual(document.res_model, created_record._name)
        self.assertEqual(document.res_id, created_record.id)
        self.assertEqual(created_record.message_main_attachment_id, document.attachment_id)
        self.assertEqual(created_record.journal_id, expected_journal)
        expected_folder = self.journal_type_labels[expected_journal.type]
        self.assertEqual(document.folder_id.name, expected_folder)
        self.assertIn(document.tag_ids.name, expected_journal.name)
