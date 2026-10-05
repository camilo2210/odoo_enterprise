# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import RecordCapturer, users
from odoo.tests.common import tagged

from odoo.addons.test_documents_full.tests.common import TestDocumentsBridgeCommon, TEXT_DATA_ATTACHMENT_VALS


@tagged("test_document_bridge")
class TestDocumentsMixin(TestDocumentsBridgeCommon):

    def _check_mixin_document_field_values(self, document):
        self.assertTrue(document.exists())
        self.assertEqual(document.res_id, self.mixin_record.id)
        self.assertEqual(document.owner_id, self.internal_user)
        self.assertEqual(document.res_model, self.mixin_record._name)
        self.assertEqual(document.access_internal, "view")
        self.assertEqual(document.access_via_link, "none")
        self.assertFalse(document.is_access_via_link_hidden)
        access = document.access_ids
        self.assertEqual(len(access), 1, "The access should have been propagated")

    @users("internal_user")
    def test_create_from_attachment_create(self):
        """Check that attachments for documents-mixin supported model sync with documents on attachment creation."""
        with RecordCapturer(self.env["documents.document"]) as doc_capturer:
            self.env["ir.attachment"].create(TEXT_DATA_ATTACHMENT_VALS | self.MIXIN_RECORD_RES_VALS)
        document = doc_capturer.records.ensure_one()
        self._check_mixin_document_field_values(document)

    @users("internal_user")
    def test_create_from_attachment_write(self):
        """Check that attachments for documents-mixin supported model sync with documents on attachment linking."""
        attachment = self.env["ir.attachment"].create(TEXT_DATA_ATTACHMENT_VALS)
        with RecordCapturer(self.env["documents.document"]) as doc_capturer:
            attachment.write(self.MIXIN_RECORD_RES_VALS)
        document = doc_capturer.records.ensure_one()
        self._check_mixin_document_field_values(document)

    def test_add_to_request_doesnt_duplicate_document(self):
        request = self.env["documents.document"].create(
            self.MIXIN_RECORD_RES_VALS
            | {"name": "request", "type": "request"}
        )
        with RecordCapturer(self.env["documents.document"]) as doc_capturer, \
                RecordCapturer(self.env["ir.attachment"]) as att_capturer:
            request.write(TEXT_DATA_ATTACHMENT_VALS)
        self.assertFalse(doc_capturer.records)
        self.assertTrue(att_capturer.records)
        self.assertEqual(request.attachment_id, att_capturer.records)
        self.assertEqual(request.attachment_id.res_model, self.MIXIN_RECORD_RES_VALS['res_model'])
        self.assertEqual(request.attachment_id.res_id, self.MIXIN_RECORD_RES_VALS['res_id'])

    def test_unlink_record(self):
        """Check processing of attachments and documents when unlinking a mixin-supported record.

        Attachments' resource fields should be linked to the document and the document sent to the Trash.
        """
        non_mixin_record = self.env["mail.test.simple.main.attachment"].create({"name": "Non Mixin Record"})
        for record in (self.mixin_record, non_mixin_record):
            with self.subTest(res_model=record._name):
                doc = self.env["documents.document"].create(TEXT_DATA_ATTACHMENT_VALS | {
                    "res_model": record._name,
                    "res_id": record.id,
                })
                self.assertEqual(doc.attachment_id.res_id, record.id)
                self.assertEqual(doc.attachment_id.res_model, record._name)

                record.unlink()

                self.assertFalse(doc.active)
                self.assertFalse(doc.res_id)
                self.assertFalse(doc.res_model)
                self.assertEqual(doc.attachment_id.res_id, doc.id)
                self.assertEqual(doc.attachment_id.res_model, "documents.document")

    def test_unlink_record_with_document_attachment_portal(self):
        """Check that an authorized portal user can delete a record with a document attachment."""
        portal_user = self.env['res.users'].create({
            'login': 'portal_user',
            'group_ids': [Command.link(self.env.ref('base.group_portal').id)],
            'name': 'Portal user'
        })
        record = self.env["mail.test.simple.main.attachment"].create({"name": ""})
        doc = self.env['documents.document'].create(TEXT_DATA_ATTACHMENT_VALS | {
            "res_model": record._name,
            "res_id": record.id,
            'folder_id': self.bridge_folder.id,
        })
        self.assertTrue(doc.active)

        record.with_user(portal_user).sudo().unlink()

        self.assertFalse(record.exists())
        self.assertTrue(doc.exists())
        self.assertFalse(doc.active)
        self.assertFalse(doc.res_id)
        self.assertFalse(doc.res_model)
        self.assertEqual(doc.attachment_id.res_id, doc.id)
        self.assertEqual(doc.attachment_id.res_model, "documents.document")
        self.assertEqual(doc.attachment_id.name, TEXT_DATA_ATTACHMENT_VALS['name'])

    def test_link_document_when_no_record_exists(self):
        """Check that a document cannot be linked to a model when no record of that model exist."""
        self.env["documents.mixin.test.model"].search([]).active = False
        self.assertFalse(self.env["documents.mixin.test.model"].search([]))
        attachment = self.env["ir.attachment"].create(TEXT_DATA_ATTACHMENT_VALS | {
            "document_ids": [Command.create({"name": "Document", "folder_id": self.bridge_folder.id})],
        })

        with self.assertRaises(UserError):
            attachment.document_ids.action_link_to_record("documents.mixin.test.model")

        record = self.env["documents.mixin.test.model"].create({"name": "Test Record 2"})
        res = attachment.document_ids.action_link_to_record("documents.mixin.test.model")
        context = res.get("context", {})
        self.assertEqual(context.get("default_resource_ref"), f"documents.mixin.test.model,{record.id}")

    def test_documents_count(self):
        with RecordCapturer(self.env["documents.document"]) as doc_capturer:
            self.env['ir.attachment'].create([
                {
                    'raw': file.encode(),
                    'name': f'{file}.txt',
                    'mimetype': 'text/plain',
                    **self.MIXIN_RECORD_RES_VALS
                } for file in ['file_1', 'file_2', 'file_3']
            ])
        documents = doc_capturer.records
        self.assertEqual(self.mixin_record.document_count, 3)
        documents[0].folder_id = False
        self.assertEqual(self.mixin_record.document_count, 3, "Count shouldn't change when documents change folder")
