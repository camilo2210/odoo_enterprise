# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mail.tests.common import MailCommon
from odoo.addons.test_documents_full.tests.common import TestDocumentsBridgeCommon
from odoo.addons.test_mail.data.test_mail_data import MAIL_EML_ATTACHMENT
from odoo.tests.common import RecordCapturer
from odoo.tools import mute_logger


class TestDocumentsMixinMulticompany(TestDocumentsBridgeCommon, MailCommon):
    """Test documents creation via mail alias in a multi-company setup.

    This tests if documents.mixin correctly handles `company_id` while getting
    the default values for document creation from a company-restricted workspace.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.bridge_folder_company_2 = cls.env['documents.document'].create({
            'name': 'Folder Records Company 2',
            'type': 'folder',
            'company_id': cls.company_2.id,
        })
        cls.company_2.documents_bridge_folder_settings = True
        cls.company_2.documents_bridge_folder_folder_id = cls.bridge_folder_company_2.id
        cls.parent_record_company_2 = cls.env["test.model.mixin.parent"].create({
            "name": "Mixin Folder Record Company 2",
            "company_id": cls.company_2.id,
            'alias_name': 'awesome-alias-folder-company-2',
        })

        cls.email_filenames = ['attachment', 'original_msg.eml']

    @mute_logger('odoo.addons.mail.models.mail_thread')
    def test_incoming_mail_to_parent_alias_attachment_company(self):
        """Test created records and documents on incoming email on a parent record alias.

        In particular, check that records have the correct company_id and that no alias domain mismatch error occurs.
        """
        subject = "I want to work for Odoo!"
        email_from = 'jobhunter@example.com'
        email_to = f'{self.parent_record_company_2.alias_id.alias_name}@{self.mail_alias_domain_c2.name}'

        with (
            self.mock_mail_gateway(),
            RecordCapturer(self.env['documents.mixin.folder.test.model'], []) as mixin_folder_capture,
            RecordCapturer(self.env['documents.document'], []) as doc_capture,
        ):
            self.format_and_process(
                MAIL_EML_ATTACHMENT,
                email_from,
                email_to,
                subject=subject,
                target_model='documents.mixin.folder.test.model',
                msg_id='<mixin-folder-company-2-test@odoo.com>',
            )

        new_record = mixin_folder_capture.records
        self.assertEqual(len(new_record), 1, "Should have created exactly one new mixin record from the email.")
        self.assertEqual(new_record.company_id.id, self.company_2.id)

        new_documents = doc_capture.records
        self.assertEqual(set(new_documents.mapped('name')), set(self.email_filenames))
        self.assertEqual(set(new_documents.mapped('type')), {'folder'})

        self.assertEqual(new_documents.folder_id, self.bridge_folder_company_2,
                         "Created folder should be in the bridge folder for company 2.")
        self.assertEqual(new_documents.company_id, self.company_2,
                         "Folder company should match the bridge's folder's company.")

        for doc in new_documents:
            self.assertIn(
                self.company_2,
                doc.alias_id.alias_domain_id.company_ids,
                f"Alias domain company for {doc.name} should include Company 2.",
            )
