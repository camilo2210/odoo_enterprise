from odoo.addons.documents_account.tests.common import DocumentsAccountActionsServerCommon
from odoo.tests.common import tagged


@tagged('post_install', '-at_install', 'test_document_bridge_full')
class TestIrActionsServerFull(DocumentsAccountActionsServerCommon):
    """Testing server actions linked to documents_account that need extra dependencies"""
    _test_user_groups = None  # FIXME list needed groups

    def test_documents_account_record_create_bank(self):
        """Test documents_account_record_create action for Bank Statements."""
        expected_journal = self.journals_by_type['bank']
        action = self.env['ir.actions.server'].create({
            'name': 'test account.bank.statement',
            'model_id': self.env['ir.model']._get_id('documents.document'),
            'state': 'documents_account_record_create',
            'documents_account_create_model': 'account.bank.statement',
            'documents_account_journal_id': expected_journal.id,
            'usage': 'documents_embedded',
        })

        document = self.document_pdf.copy()
        document.folder_id._embed_action(action.id)
        self._run_action_and_assert_sync(action, document, expected_journal)

    def test_documents_account_standard_actions_bank(self):
        """Test the pre-configured bank financial server actions."""
        finance_folder = self.env.ref('documents.document_finance_folder')
        document = self.document_pdf.copy()
        document.folder_id = finance_folder

        action_xml_ids = self.actions_by_type.get('bank', [])
        self.assertTrue(action_xml_ids)
        for action_xml_id in action_xml_ids:

            action = self.env.ref(action_xml_id)
            expected_journal = self.journals_by_type['bank']

            with self.subTest(action_name=action.name):
                self._run_action_and_assert_sync(action, document.copy(), expected_journal)
