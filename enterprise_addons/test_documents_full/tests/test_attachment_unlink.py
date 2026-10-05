# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments
from odoo.tests import RecordCapturer, users


class TestAttachmentUnlink(TransactionCaseDocuments):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.records = cls.env['mail.test.simple.main.attachment'].create([{'name': f'test{idx}'} for idx in range(2)])
        cls.documents = (cls.document_gif | cls.document_txt)
        for idx, record in enumerate(cls.records):
            cls.documents[idx].write({
                'res_model': record._name,
                'res_id': record.id,
            })
        cls.attachments = cls.documents.attachment_id
        cls.attachments_raw = cls.documents.attachment_id.mapped(lambda a: a.raw.content)

    def test_initial_data(self):
        self.assertEqual(len(self.attachments), 2)
        self.assertTrue(all(raw for raw in self.attachments_raw), "Document contents are not empty")

    def check_archive_on_attachment_deletion(self, res_model, capture_msg=None):
        """Check that documents are in the Trash linked to a copy of their attachments and a res_model record."""
        for doc, attachment, attachment_raw in zip(self.documents, self.attachments, self.attachments_raw):
            self.assertFalse(attachment.exists(), 'The attachment is deleted to not disrupt other flows')
            self.assertTrue(doc.exists())
            self.assertEqual(doc.attachment_id.raw.content, attachment_raw,
                             'The copied attachment has the same datas')
            self.assertEqual(
                (doc.attachment_id.res_model, doc.attachment_id.res_id), ('documents.document', doc.id),
                'The copied attachment is linked to the document and not to the original model')
            self.assertFalse(doc.active, 'The document is in the trash')
            if not res_model:
                self.assertFalse(doc.res_model, 'Document should not be linked to a parent record')
            else:
                self.assertEqual(doc.res_model, res_model, 'The document should stay linked to parent record')
            if capture_msg:
                log_message = capture_msg.records.filtered(lambda m: m.model == doc._name and m.res_id == doc.id)
                self.assertEqual(len(log_message), 1)
                self.assertEqual(log_message.body, '<p>Document archived because its reference record was deleted.</p>')

    @users('documents@example.com')
    def test_archive_on_attachment_deletion(self):
        """Deleting a document attachment moves the document in the Trash (linked to a copy of its attachment)."""
        self.documents = self.documents.with_env(self.env)
        with RecordCapturer(self.env['mail.message']) as capture_msg:
            # Deleting document attachments linked to another model must move the document to the trash
            self.documents.attachment_id.unlink()
        self.check_archive_on_attachment_deletion('mail.test.simple.main.attachment', capture_msg)
        # Deleting archived document attachments solely linked to a document must keep the document in the trash
        self.assertTrue(self.documents.attachment_id)
        with RecordCapturer(self.env['mail.message']) as capture_msg:
            self.documents.attachment_id.unlink()
        self.assertFalse(capture_msg.records, "No log should be added on archived document.")
        self.check_archive_on_attachment_deletion('mail.test.simple.main.attachment', None)
        # Deleting document attachments solely linked to a document must move the document to the trash
        self.documents.active = True
        with RecordCapturer(self.env['mail.message']) as capture_msg:
            self.documents.attachment_id.unlink()
        self.check_archive_on_attachment_deletion('mail.test.simple.main.attachment', capture_msg)
        # Deleting the documents must delete the attachments
        self.documents[0].active = True
        self.assertEqual(self.documents.mapped('active'), [True, False])
        with RecordCapturer(self.env['ir.attachment'].sudo()) as capture_attachment:
            self.documents.unlink()
        self.assertFalse(capture_attachment.records)
        self.assertFalse(any(a.exists() for a in self.attachments))

    @users('documents@example.com')
    def test_archive_on_cascade_deletion(self):
        """Test cascade deletion: record -> attachment -> related document archived"""
        self.documents = self.documents.with_env(self.env)
        # Using mail.thread.main.attachment as record model allows to test that the document write method doesn't fail
        # because accessing the deleted record. See remark in IrAttachment.unlink_archive_document.
        self.assertTrue(self.records.pool[self.records._name], self.records.pool['mail.thread.main.attachment'])
        attachment_no_document = self.env['ir.attachment'].with_context(no_document=True).create(
            {'name': 'Test Attachment', 'raw': b'test', 'res_model': self.records._name, 'res_id': self.records[0].id})
        with RecordCapturer(self.env['mail.message']) as capture_msg, \
                RecordCapturer(self.env['ir.attachment'].sudo()) as capture_attachment:
            self.records.unlink()
        self.check_archive_on_attachment_deletion(False, capture_msg)
        self.assertFalse(attachment_no_document.exists(), "The attachment not linked to a document is cascade deleted")
        self.assertEqual(capture_attachment.records, self.documents.attachment_id,
                         "Attachments linked to documents are duplicated")
