# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import RecordCapturer
from odoo.tests.common import tagged

from odoo.addons.test_documents_full.tests.common import TestDocumentsBridgeCommon, TEXT_DATA_ATTACHMENT_VALS


@tagged("test_document_bridge")
class TestDocumentsBridge(TestDocumentsBridgeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_2 = cls.env["res.company"].create({"name": "Company 2"})
        cls.folder_company_2 = cls.env["documents.document"].create({
            "name": "Folder Company 2",
            "type": "folder",
            "company_id": cls.company_2.id,
        })
        cls.company_2.documents_bridge_folder_id = cls.folder_company_2

    def test_check_create_documents_company_settings(self):
        """Check that disabling the bridge in company settings prevents sync with documents."""
        company = self.env.user.company_id
        company.documents_bridge_settings = False
        with RecordCapturer(self.env["documents.document"]) as doc_capturer:
            self.env["ir.attachment"].create(TEXT_DATA_ATTACHMENT_VALS | self.MIXIN_RECORD_RES_VALS)
        self.assertFalse(doc_capturer.records)

    def test_reset_default_documents_folder_id(self):
        """Check the update of folder_id when the bridge is enabled/disabled on a company."""
        new_company = self.env["res.company"].create({"name": "New Company", "documents_bridge_settings": True})
        self.assertEqual(new_company.documents_bridge_folder_id, self.bridge_folder)
        test_companies = self.env.company + new_company
        # Only our two test companies should use this folder
        (self.env["res.company"].sudo().search([]) - test_companies).documents_bridge_folder_id = False

        folder_2 = self.env["documents.document"].create({"name": "Test Folder 2", "type": "folder"})

        self.env.company.documents_bridge_settings = False
        self.assertEqual(
            test_companies.with_context(allowed_company_ids=test_companies.ids).documents_bridge_folder_id,
            self.bridge_folder,
            "Both companies should still be linked to Test Folder"
        )

        new_company.documents_bridge_folder_id = folder_2
        self.bridge_folder.action_archive()

        new_company.documents_bridge_settings = False
        self.assertEqual(
            new_company.documents_bridge_folder_id,
            folder_2,
            "The folder should still be linked with disabled bridge"
        )
        new_company.documents_bridge_settings = True
        self.assertEqual(new_company.documents_bridge_folder_id, folder_2)
        new_company.documents_bridge_settings = False
        folder_2.unlink()
        new_company.documents_bridge_settings = True
        self.assertFalse(new_company.documents_bridge_folder_id, "Not expected as the default is archived")
        new_company.documents_bridge_settings = False
        self.bridge_folder.action_unarchive()
        new_company.documents_bridge_settings = True
        self.assertEqual(
            new_company.documents_bridge_folder_id,
            self.bridge_folder,
            "The default folder should have been re-used"
        )

    def test_unlink_company_used_folder(self):
        """Check that folders used for a bridge are protected from deletion (see _raise_if_used_folder) """
        self.assertTrue(self.env.company.documents_bridge_settings)

        with self.assertRaises(UserError):
            self.env.company.documents_bridge_folder_id.action_archive()

        with self.assertRaises(UserError):
            self.env.company.documents_bridge_folder_id.unlink()

        self.env.company.documents_bridge_settings = False
        self.env.company.documents_bridge_folder_id.action_archive()
        self.env.company.documents_bridge_folder_id.unlink()
