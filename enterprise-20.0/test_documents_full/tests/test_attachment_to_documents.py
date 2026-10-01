# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError
from odoo.tests import RecordCapturer, users

from odoo.addons.test_documents_full.tests.common import TestDocumentsBridgeCommon, TEXT_DATA_ATTACHMENT_VALS


class TestAttachmentToDocument(TestDocumentsBridgeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attachment_id = cls.env['ir.attachment'].with_context(no_document=True).create(
            TEXT_DATA_ATTACHMENT_VALS | cls.MIXIN_RECORD_RES_VALS
        )

    @users('internal_user')
    def test_create_document(self):
        attachment_as_internal = self.attachment_id.with_user(self.internal_user)
        attachment_no_record = self.env['ir.attachment'].create(TEXT_DATA_ATTACHMENT_VALS)
        model = self.env["ir.model"]._get("documents.mixin.test.model")
        accesses = self.env["ir.access"].sudo().search([("model_id", "=", model.id)])
        for attachment, bridge_enabled, permissions, should_create_linked_document in (
            (attachment_as_internal,        False,        'ru',                         False),
            (attachment_as_internal,         True,         'd',                         False),
            (attachment_as_internal,         True,         'r',                         False),
            (attachment_as_internal,         True,        'ru',                          True),
            (  attachment_no_record,         True,        'ru',                         False),
        ):
            with self.subTest(attachment=attachment, bridge_enabled=bridge_enabled, permissions=permissions):
                self.company.documents_bridge_settings = bridge_enabled
                accesses.operation = permissions
                if 'r' not in permissions:
                    with self.assertRaises(AccessError):
                        attachment.create_document()
                    continue

                with (RecordCapturer(self.env['documents.document']) as document_capture,
                      RecordCapturer(self.env['ir.attachment']) as attachment_capture):
                    attachment.create_document()

                document = document_capture.records.ensure_one()
                if not should_create_linked_document:
                    self.assertNotEqual(document.attachment_id, attachment)
                    self.assertTrue(attachment_capture.records)
                    self.assertEqual(attachment_capture.records, document.attachment_id)
                    self.assertEqual(document.user_folder_id, "MY")
                else:
                    self.assertEqual(document.attachment_id, attachment)
                    self.assertFalse(attachment_capture.records)
                    self.assertEqual(document.folder_id, self.env.company.documents_bridge_folder_id)

    def test_attachments_without_documents_have_no_linked_document_id(self):
        """
        Test the batch computation of linked_document_id on attachments sharing
        the same res_id and verify that linked_document_id remains unset when no
        document is associated with the attachments.
        """
        attachments = self.attachment_id | self.attachment_id.copy()

        self.assertFalse(attachments.document_ids)
        self.assertFalse(attachments.linked_document_id)

    def test_document_count(self):
        attachment = self.env["ir.attachment"].create(
            {"name": "foo", "raw": b"foo", "res_id": self.mixin_record.id, "res_model": self.mixin_record._name}
        )
        self.assertEqual(self.mixin_record.document_count, 1)
        attachment.unlink()
        self.assertEqual(self.mixin_record.document_count, 0)
