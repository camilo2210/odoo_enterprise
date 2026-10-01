# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from unittest import skip
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http.requestlib import DEFAULT_MAX_CONTENT_LENGTH
from odoo.tests import users
from odoo.tests.common import new_test_user, RecordCapturer
from odoo.tools import html2plaintext, mute_logger

from .test_documents_common import TransactionCaseDocuments, get_document_creation_message
from odoo.addons.base.tests.files import GIF_RAW, WEBP_RAW
from odoo.addons.mail.tests.common import MailCommon

TEXT_RAW = b'TEST'


class TestCaseDocuments(TransactionCaseDocuments, MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_company_root = cls.env['documents.document'].create({
            'type': 'binary',
            'raw': GIF_RAW,
            'name': 'company_root.gif',
            'mimetype': 'image/gif',
            'folder_id': False,
            'owner_id': False,
            'access_ids': [Command.create({'partner_id': cls.document_manager.partner_id.id, 'role': 'edit'}),
                           Command.create({'partner_id': cls.internal_user.partner_id.id, 'role': 'edit'})],
        })

    @skip("TODO: move to controller")
    @users('documents@example.com')
    def test_documents_action_log_access_archived(self):
        access = self.env['documents.access'].search([
            ('document_id', '=', self.document_txt.id),
            ('partner_id', '=', self.env.user.partner_id.id),
        ])
        self.assertFalse(access)
        self.document_txt.action_archive()
        self.env['documents.document'].action_log_access(
            self.document_txt.access_token)
        access = self.env['documents.access'].search([
            ('document_id', '=', self.document_txt.id),
            ('partner_id', '=', self.env.user.partner_id.id),
        ])
        self.assertTrue(access)

    def test_documents_action_create_shortcut(self):
        # Make sure we test copying m2o too
        self.document_gif.partner_id = self.env.user.partner_id
        shortcut = self.document_gif.action_create_shortcut()
        self.assertFalse(shortcut.attachment_id)
        original_file_size = self.document_gif.file_size
        for field_name in self.env['documents.document']._get_shortcuts_copy_fields():
            with self.subTest(field_name=field_name):
                self.assertEqual(shortcut[field_name], self.document_gif[field_name])
        attachment = self.env['ir.attachment'].create({
            'name': 'attached',
            'raw': b'aaaaa',
            'res_model': False,
            'res_id': False,
        })
        self.document_gif.attachment_id = attachment
        self.assertNotEqual(self.document_gif.file_size, original_file_size)
        self.assertEqual(shortcut.file_size, self.document_gif.file_size)
        self.assertEqual(shortcut.file_extension, self.document_gif.file_extension)

    def test_documents_action_delete_from_history(self):
        """Test the `action_delete_from_history` action of documents."""
        current_attachment = self.document_gif.attachment_id

        # We can not delete the attachment if the history is empty
        with self.assertRaises(UserError):
            self.document_gif.action_delete_from_history(current_attachment.id)
        self.assertTrue(current_attachment.exists())

        new_attachment, other_attachment = self.env['ir.attachment'].create([{'name': 'Test'}] * 2)
        self.document_gif.previous_attachment_ids = new_attachment

        # We can not delete the attachment if it's not in the history of the document
        with self.assertRaises(UserError):
            self.document_gif.action_delete_from_history(other_attachment.id)
        self.assertTrue(current_attachment.exists())
        self.assertTrue(new_attachment.exists())
        self.assertTrue(other_attachment.exists())

        # Delete the history version delete the attachment
        self.document_gif.action_delete_from_history(new_attachment.id)
        self.assertFalse(new_attachment.exists(), "The attachment should have been deleted")
        self.assertTrue(current_attachment.exists())

        # Deleting the current attachment restore the most recent version
        current_attachment = self.document_gif.attachment_id
        versions = self.env['ir.attachment'].create([{'name': 'Test'}] * 3)
        self.document_gif.previous_attachment_ids = versions
        self.document_gif.action_delete_from_history(current_attachment.id)
        self.assertFalse(current_attachment.exists())
        self.assertEqual(self.document_gif.attachment_id.id, max(versions.ids))

    def test_documents_create_from_attachment(self):
        """
        Tests a documents.document create method when created from an already existing ir.attachment.
        """
        attachment = self.env['ir.attachment'].create({
            'raw': GIF_RAW,
            'name': 'attachmentGif.gif',
            'res_model': 'documents.document',
            'res_id': 0,
        })
        with self.mock_mail_app():
            document_a = self.env['documents.document'].create({
                'folder_id': self.folder_b.id,
                'name': 'new name',
                'attachment_id': attachment.id,
            })
        self.assertEqual(document_a.attachment_id.id, attachment.id,
                         'the attachment should be the attachment given in the create values')
        self.assertEqual(document_a.name, 'new name',
                         'the name given should be used')
        self.assertFalse(document_a.res_model)
        self.assertFalse(document_a.res_id)
        self.assertTrue(self._new_msgs)

    def test_documents_create_res_model(self):
        """Test the model set on a document and its attachment."""
        attachment = self.env['ir.attachment'].create({'name': 'test', 'res_model': 'documents.document'})
        doc = self.env['documents.document'].create({'attachment_id': attachment.id})
        self.assertEqual(attachment.res_model, 'documents.document')
        self.assertEqual(attachment.res_id, doc.id)

        attachment = self.env['ir.attachment'].create({'name': 'test', 'res_model': 'documents.document'})
        partner = self.env['res.partner'].create({'name': 'partner'})
        with self.mock_mail_app():
            doc = self.env['documents.document'].create({'attachment_id': attachment.id, 'res_model': 'res.partner', 'res_id': partner.id})
        self.assertEqual(attachment.res_model, 'res.partner')
        self.assertEqual(attachment.res_id, partner.id)
        self.assertEqual(doc.res_model, 'res.partner')
        self.assertEqual(doc.res_id, partner.id)
        self.assertTrue(self._new_msgs)
        self.assertMessageFields(self._new_msgs, {'body_content': get_document_creation_message('OdooBot', 'test', 'Contact')})

        user = self.portal_user
        attachment = self.env['ir.attachment'].create({'name': 'test', 'res_model': 'res.users', 'res_id': user.id})
        doc = self.env['documents.document'].create({'attachment_id': attachment.id})
        self.assertEqual(attachment.res_id, user.id)
        self.assertEqual(doc.res_model, 'res.users')
        self.assertEqual(doc.res_id, user.id)

        doc.attachment_id = False
        doc.name = 'test'
        doc.raw = b'data'
        self.assertEqual(doc.attachment_id.res_model, 'res.users')
        self.assertEqual(doc.attachment_id.res_id, user.id)
        self.assertEqual(doc.attachment_id.name, 'test')

        doc.write({'attachment_id': False, 'res_model': False, 'res_id': False})
        doc.raw = b'data'
        self.assertEqual(doc.attachment_id.res_model, 'documents.document')
        self.assertEqual(doc.attachment_id.res_id, doc.id)
        self.assertEqual(doc.attachment_id.name, 'test')

        doc = self.env['documents.document'].create({'raw': b'data'})
        self.assertFalse(doc.res_model)
        self.assertFalse(doc.res_id)
        self.assertEqual(doc.attachment_id.res_model, 'documents.document')
        self.assertEqual(doc.attachment_id.res_id, doc.id)

    @users('documents@example.com')
    def test_documents_create_write(self):
        """
        Tests a documents.document create and write method,
        documents should automatically create a new ir.attachments in relevant cases.
        """
        document_a = self.env['documents.document'].create({
            'name': 'Test mimetype gif',
            'raw': GIF_RAW,
            'folder_id': self.folder_b.id,
        })
        self.assertFalse(document_a.res_model)
        self.assertFalse(document_a.res_id)
        self.assertEqual(document_a.attachment_id.res_model, 'documents.document',
                         'the res_model should be set as document by default')
        self.assertEqual(document_a.attachment_id.res_id, document_a.id,
                         'the res_id should be set as the document id by default to allow access right inheritance')
        self.assertEqual(document_a.attachment_id.raw.content, GIF_RAW, 'the document should have a GIF data')
        document_no_attachment = self.env['documents.document'].create({
            'name': 'Test mimetype gif',
            'folder_id': self.folder_b.id,
            'type': 'request',
        })
        self.assertFalse(document_no_attachment.attachment_id, 'the new document shouldnt have any attachment_id')
        document_no_attachment.write({'raw': TEXT_RAW})
        self.assertEqual(document_no_attachment.attachment_id.raw.content, TEXT_RAW, 'the document should have an attachment')
        self.assertEqual(document_no_attachment.type, 'binary')

    def test_documents_create_performance(self):
        folders = self.env['documents.document'].create([
            {'type': 'folder', 'name': f'Folder {i}', 'access_internal': 'view'}
            for i in range(50)
        ])
        folders.flush_recordset()
        folders.invalidate_recordset()
        with self.assertQueryCount(161):
            self.env['documents.document'].create([{
                'folder_id': folder.id,
                'type': 'binary',
                'raw': 'test',
            } for folder in folders])

    def test_default_res_id_model(self):
        """
        Test default res_id and res_model from context are used for linking attachment to document.
        """
        document = self.env['documents.document'].create({
            'type': 'request',
            'folder_id': self.folder_b.id,
        })
        attachment = self.env['ir.attachment'].with_context(
            default_res_id=document.id,
            default_res_model=document._name,
        ).create({
            'name': 'attachmentGif.gif',
            'raw': GIF_RAW,
        })
        self.assertEqual(attachment.res_id, document.id, "It should be linked to the default res_id")
        self.assertEqual(attachment.res_model, document._name, "It should be linked to the default res_model")
        self.assertEqual(document.attachment_id, attachment, "Document should be linked to the created attachment")

    @users('documents@example.com')
    def test_versioning(self):
        """
        Tests the versioning/history of documents
        """
        document = self.env["documents.document"].create(
            {
                "raw": GIF_RAW,
                "folder_id": self.folder_b.id,
                "res_model": "res.users",
                "res_id": self.doc_user.id,
            }
        )

        def check_attachment_res_fields(
            attachment, expected_res_model, expected_res_id
        ):
            self.assertEqual(
                attachment.res_model,
                expected_res_model,
                "The attachment should be linked to the right model",
            )
            self.assertEqual(
                attachment.res_id,
                expected_res_id,
                "The attachment should be linked to the right record",
            )

        self.assertEqual(len(document.previous_attachment_ids.ids), 0, "The history should be empty")
        original_attachment = document.attachment_id
        check_attachment_res_fields(original_attachment, "res.users", self.doc_user.id)
        document.write({'raw': TEXT_RAW})
        new_attachment = document.previous_attachment_ids
        check_attachment_res_fields(original_attachment, "res.users", self.doc_user.id)
        check_attachment_res_fields(new_attachment, "documents.document", document.id)
        self.assertEqual(len(document.previous_attachment_ids), 1)
        self.assertNotEqual(document.previous_attachment_ids, original_attachment)
        self.assertEqual(document.previous_attachment_ids[0].raw.content, GIF_RAW, "The history should have the right content")
        self.assertEqual(document.attachment_id.raw.content, TEXT_RAW, "The document should have the right content")
        old_attachment = document.attachment_id
        document.write({'attachment_id': new_attachment.id})
        check_attachment_res_fields(new_attachment, "res.users", self.doc_user.id)
        check_attachment_res_fields(old_attachment, "documents.document", document.id)
        self.assertEqual(document.attachment_id.id, new_attachment.id, "the document should contain the new attachment")
        self.assertEqual(document.previous_attachment_ids, original_attachment, "the history should contain the original attachment")
        document.write({"attachment_id": document.attachment_id.id})
        check_attachment_res_fields(new_attachment, "res.users", self.doc_user.id)
        self.assertEqual(
            document.attachment_id.id,
            new_attachment.id,
            "the document attachment should not have changed",
        )
        self.assertTrue(
            new_attachment not in document.previous_attachment_ids,
            "the history should not contain the new attachment",
        )
        document.write({'raw': GIF_RAW})
        self.assertEqual(document.attachment_id, new_attachment)

    def test_write_mimetype(self):
        """
        Tests the consistency of documents' mimetypes
        """
        document = self.env['documents.document'].with_user(self.doc_user.id).create({'raw': GIF_RAW, 'folder_id': self.folder_b.id})
        document.with_user(self.doc_user.id).write({'raw': TEXT_RAW, 'mimetype': 'text/plain'})
        self.assertEqual(document.mimetype, 'text/plain', "the new mimetype should be the one given on write")
        document.with_user(self.doc_user.id).write({'raw': TEXT_RAW, 'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})
        self.assertEqual(document.mimetype, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', "should preserve office mime type")

    def test_archive_on_attachment_deletion(self):
        """
        Makes sure that documents are archived when their attachment is unlinked.
        """
        document = self.env['documents.document'].create({'raw': GIF_RAW, 'folder_id': self.folder_b.id})
        self.assertTrue(document.exists() and document.active, 'the document should exist and not be archived')
        document.attachment_id.unlink()
        self.assertTrue(document.exists() and not document.active, 'the document should exist and be archived')

    def test_archive_request_on_unlink_related_activity(self):
        """
        Makes sure that document requests are archived when their related activity are deleted.
        """
        record = self.env['res.partner'].create({'name': 'test record'})
        upload_activity_type_xml_id = 'mail.mail_activity_data_upload_document'
        self.env.ref(upload_activity_type_xml_id).folder_id = self.folder_a
        with RecordCapturer(self.env['documents.document']) as capture:
            record.activity_schedule(upload_activity_type_xml_id)
        document = capture.records.filtered(lambda d: d.request_activity_id == record.activity_ids)
        activity = document.request_activity_id
        self.assertTrue(activity)
        self.assertEqual(len(document), 1, "Scheduling an upload activity creates a related document request")
        record.unlink()
        self.assertFalse(activity.with_context(active_test=False).exists(),
                         "Activity is deleted as its related record is deleted")
        self.assertTrue(document.exists() and not document.active,
                        "The document request is archived as its related activity is deleted")

    def test_is_favorited(self):
        """ Test the is_favorited field (compute and inverse method). """
        # Test the compute method
        self.document_gif.favorited_ids = self.doc_user
        self.assertFalse(self.document_gif.is_favorited)
        self.assertTrue(self.document_gif.with_user(self.doc_user).is_favorited)
        # Test the inverse method
        documents = self.document_gif | self.document_txt
        documents.with_user(self.doc_user).is_favorited = True
        documents.invalidate_recordset()
        self.assertEqual(documents.with_user(self.doc_user).mapped('is_favorited'), [True, True])
        self.assertEqual(documents.mapped('is_favorited'), [False, False])
        documents.with_user(self.doc_user).is_favorited = False
        documents.invalidate_recordset()
        self.assertEqual(documents.with_user(self.doc_user).mapped('is_favorited'), [False, False])
        self.assertEqual(documents.mapped('is_favorited'), [False, False])

    def test_neuter_mimetype(self):
        """
        Tests that potentially harmful mimetypes (XML mimetypes that can lead to XSS attacks) are converted to text

        In fact this logic is implemented in the base `IrAttachment` model but was originally duplicated.
        The test stays duplicated here to ensure the de-duplicated logic still catches our use cases.
        """
        self.folder_b.action_update_access_rights(partners={self.doc_user.partner_id: ('edit', False)})
        document = self.env['documents.document'].create({'raw': GIF_RAW, 'folder_id': self.folder_b.id})

        document.with_user(self.doc_user.id).write({'raw': TEXT_RAW, 'mimetype': 'text/xml'})
        self.assertEqual(document.mimetype, 'text/plain', "XML mimetype should be forced to text")
        document.with_user(self.doc_user.id).write({'raw': TEXT_RAW, 'mimetype': 'image/svg+xml'})
        self.assertEqual(document.mimetype, 'text/plain', "SVG mimetype should be forced to text")
        document.with_user(self.doc_user.id).write({'raw': TEXT_RAW, 'mimetype': 'text/html'})
        self.assertEqual(document.mimetype, 'text/plain', "HTML mimetype should be forced to text")
        document.with_user(self.doc_user.id).write({'raw': TEXT_RAW, 'mimetype': 'application/xhtml+xml'})
        self.assertEqual(document.mimetype, 'text/plain', "XHTML mimetype should be forced to text")

    def test_create_from_message_invalid_tags(self):
        """
        Create a new document from message with a deleted tag, it should keep only existing tags.
        """
        message = self.env['documents.document'].message_new({
            'subject': 'Test',
        }, {
            'tag_ids': [(6, 0, [self.tag_b.id, -1])],
            'folder_id': self.folder_a.id,
        })
        self.assertEqual(message.tag_ids.ids, [self.tag_b.id], "Should only keep the existing tag")

    def test_file_extension(self):
        """ Test the detection of the file extension and its edition. """
        sanitized_extension = 'txt'
        for extension in ('.txt', ' .txt', '..txt', '.txt ', ' .txt ', '  .txt   '):
            document = self.env['documents.document'].create({
                'raw': b"Test",
                'name': f'name{extension}',
                'mimetype': 'text/plain',
                'folder_id': self.folder_b.id,
            })
            self.assertEqual(document.file_extension, sanitized_extension,
                             f'"{extension}" must be sanitized to "{sanitized_extension}" at creation')
        for extension in ('txt', '  txt', '  txt   ', '.txt', ' .txt', ' .txt  ', '..txt', '  ..txt '):
            document.file_extension = extension
            self.assertEqual(document.file_extension, sanitized_extension,
                             f'"{extension}" must be sanitized to "{sanitized_extension}" at edition')

        # test extension when filename is changed (i.e. name is edited or file is replaced)
        document.name = 'test.png'
        self.assertEqual(document.file_extension, 'png', "extension must be updated on change in filename")

    def test_restricted_folder_multi_company(self):
        """
        Tests the behavior of a restricted folder in a multi-company environment
        """

        company_a = self.env.company
        company_b = self.env['res.company'].create({'name': 'Company B'})

        user_b = self.env['res.users'].create({
            'name': 'User of company B',
            'login': 'user_b',
            'group_ids': [(6, 0, [self.ref('documents.group_documents_manager')])],
            'company_id': company_b.id,
            'company_ids': [(6, 0, [company_b.id])]
        })

        self.folder_a.company_id = company_a
        self.assertEqual(self.folder_a.display_name, 'folder A',
                         "The parent folder's name should not be hidden")
        self.assertEqual(self.folder_a.with_user(user_b).display_name, 'Restricted',
                         "The parent folder's name should be hidden")
        self.assertEqual(self.folder_a_a.display_name, "folder A - A",
                         "The parent folder name should not be included in the name")

    def test_unlink_attachments_with_documents(self):
        """
        Tests a documents.document unlink method.
        Attachments should be deleted when related documents are deleted,
        for which res_model is not 'documents.document' or `False`.

        Test case description:
            Case 1:
            - upload a document with res_model 'res.partner'.
            - check if attachment exists.
            - unlink the document.
            - check if attachment exists or not.

            Case 2:
            - ensure the existing flow for res_model 'documents.document'
              does not break.

            Case 3:
            - ensure the existing flow for res_model `False` does not break.
        """
        documents = self.env['documents.document'].create([{
                'raw': GIF_RAW,
                'folder_id': self.folder_b.id,
                'res_model': res_model,
                'res_id': res_id,
            } for res_model, res_id in (('res.partner', self.internal_user.partner_id.id), (False, False))
        ])
        self.assertFalse(documents[1].res_model)
        self.assertEqual(documents[1].attachment_id.res_model, 'documents.document')
        for document in documents:
            with self.subTest(res_model=document.res_model):
                self.assertTrue(document.attachment_id.exists())
                attachment = document.attachment_id
                document.unlink()
                self.assertFalse(attachment.exists())

    def test_archive_and_unarchive_document(self):
        self.document_txt.action_archive()
        self.assertFalse(self.document_txt.active, 'the document should be inactive')
        self.document_txt.action_unarchive()
        self.assertTrue(self.document_txt.active, 'the document should be active')

    def test_archived_documents_operations(self):
        """Check (un)authorized moves of archived documents"""
        # Initial set up:
        #
        # folder_1
        # ├─ folder_3
        # │  ├─ request
        # folder_2
        folder_1, folder_2, folder_3 = self.env['documents.document'].create([
            {'name': f'Test Folder {idx + 1}', 'type': 'folder'} for idx in range(3)
        ])
        folder_3.folder_id = folder_1
        request = self.env['documents.document'].create({
            'name': 'Test Request',
            'folder_id': folder_3.id,
            'type': 'request',
        })

        # Can't move into archived folders
        folder_2.action_archive()
        with self.assertRaises(UserError):
            folder_3.folder_id = folder_2
        folder_2.action_unarchive()

        # No-op doesn't fail
        folder_1.action_archive()
        folder_3.folder_id = folder_1

        # Can't simply move archived documents
        with self.assertRaises(UserError):
            folder_3.folder_id = folder_2
        with self.assertRaises(UserError):
            folder_3.user_folder_id = str(folder_2.id)

        # Move is allowed if specifying `active` as well (without children) *if the current folder is active*
        with self.assertRaises(UserError):
            folder_3.write({'folder_id': folder_2.id, 'active': True})
        (folder_1 | folder_3).write({'folder_id': folder_2.id, 'active': True})

        self.assertFalse(request.active, "folder_3's content should still be in the trash")

    def test_log_message_on_doc_move_to_my_drive(self):
        """Moving a document to My Drive logs a message on the source folder."""
        source_folder_id = self.document_txt.folder_id.id
        with RecordCapturer(self.env['mail.message'], []) as capture:
            self.document_txt.with_user(self.document_manager).write({'user_folder_id': 'MY'})
            message = capture.records

        self.assertEqual(len(message), 1)
        self.assertEqual(message.res_id, source_folder_id)
        self.assertIn("file.txt has been moved outside this folder.", html2plaintext(message.body))

    def test_unarchive_document_with_archived_parent(self):
        """Unarchive a document whose parent folder is archived should send an error."""
        document = self.document_txt

        def check_error_message(document):
            with self.assertRaises(UserError) as err:
                document.action_unarchive()
            self.assertEqual(
                err.exception.args[0],
                "Item(s) you wish to restore are included in archived folders. "
                "To restore these items, you must restore the following including folders instead:"
                "\n"
                "- folder B"
            )

        self.folder_b.folder_id = self.folder_a  # when the parent has folder_id
        self.folder_b.action_archive()
        check_error_message(document)

        self.folder_b.folder_id = False  # when the parent has folder_id False
        check_error_message(document)

    def test_delete_document(self):
        self.document_txt.action_archive()
        self.assertFalse(self.document_txt.active, 'the document should be inactive')
        self.document_txt.unlink()
        self.assertFalse(self.document_txt.exists(), 'the document should not exist')

    def test_copy_document(self):
        @contextmanager
        def patched_compute_methods():
            fields_to_recompute = self.env['documents.document']._get_fields_to_recompute(depends=['attachment_id'])
            self.assertSetEqual({f.name for f in fields_to_recompute}, {
                'name',
                'is_multipage',
                'thumbnail',
                'thumbnail_status',
                'url_preview_image',
                'file_extension',
            })
            # A compute method might be used by multiple fields,
            # and we can't doubly mock the same compute
            computes_to_mock = defaultdict(list)
            for field in fields_to_recompute:
                computes_to_mock[field.compute].append(field)
            with ExitStack() as stack:
                for compute, fields in computes_to_mock.items():
                    stack.enter_context(patch.object(
                        self.registry['documents.document'],
                        compute,
                        autospec=True,
                        side_effect=self.failureException(
                            f"The compute stored field `{'|'.join(f.name for f in fields)}` must not be triggered "
                            "after a copy upon flushing, its value should be just copied or explicitly set."
                        ),
                    ))
                yield

        with patched_compute_methods():
            with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
                copy = self.document_txt.copy()
            self.assertEqual(copy.name, "file.txt (copy)")
            self.assertNotEqual(
                copy.attachment_id.ensure_one().id,
                self.document_txt.attachment_id.id,
                "There must be a new attachment"
            )
            self.assertEqual(copy.raw.content, self.document_txt.raw.content)

            self.env.flush_all()  # trigger recomputes

            self.assertEqual(copy.is_multipage, self.document_txt.is_multipage)

        with mute_logger('odoo.addons.documents.models.documents_document'):  # Creating document(s) as superuser
            copy_with_default = self.document_txt.copy({"name": "test"})
        self.assertEqual(copy_with_default.name, "test")
        self.assertNotEqual(
            copy.attachment_id.ensure_one().id,
            self.document_txt.attachment_id.id,
            "There must be a new attachment"
        )
        self.assertEqual(copy.raw.content, self.document_txt.raw.content)

        # check that we can copy in a folder inside the company folder
        self.assertFalse(self.folder_a.folder_id)
        self.folder_a.owner_id = False
        self.folder_a.access_internal = 'edit'

        # Special case where we can not write, but `user_permission == edit` because
        # the folder is in the company root
        with self.assertRaises(AccessError):
            self.folder_a.with_user(self.internal_user).check_access('write')
        self.assertEqual(self.folder_a.with_user(self.internal_user).user_permission, 'edit')

        self.document_txt.folder_id = self.folder_a
        self.document_txt.with_user(self.internal_user).copy()

        # copy in batch documents of different folder
        self.assertNotEqual(self.document_txt.folder_id, self.document_gif.folder_id)
        copied_documents = (self.document_txt | self.document_gif).with_user(self.internal_user).copy()
        self.assertEqual(copied_documents[0].name, f'{self.document_txt.name} (copy)')
        self.assertEqual(copied_documents[1].name, f'{self.document_gif.name} (copy)')

        # Check that copied documents res_model and res_id are pointing to themselves
        document_txt_copy = self.document_txt.with_user(self.internal_user).copy()
        copied_documents = (self.document_txt | document_txt_copy).with_user(self.internal_user).copy()
        self.document_txt.unlink()
        for copied_document in copied_documents:
            self.assertFalse(copied_document.res_id)
            self.assertFalse(copied_document.res_model)
            self.assertEqual(copied_document.attachment_id.res_id, copied_document.id)
            self.assertEqual(copied_document.attachment_id.res_model, "documents.document")
            self.assertTrue(copied_document.exists())

        self.document_gif.write({
            "res_model": "res.partner",
            "res_id": self.env.user.partner_id.id,
        })
        with mute_logger('odoo.addons.documents.models.documents_document'):
            copied_document = self.document_gif.copy()
        self.assertFalse(copied_document.res_id, copied_document.id)
        self.assertFalse(copied_document.res_model)
        self.assertEqual(copied_document.attachment_id.res_id, copied_document.id)
        self.assertEqual(copied_document.attachment_id.res_model, "documents.document")

    def test_copy_document_company_to_company(self):
        """ Manager can copy both the company-root folder and doc to company-root. """
        copied_folder = self.company_root_folder.with_user(self.document_manager).copy(default={'user_folder_id': 'COMPANY'})
        self.assertTrue(copied_folder)
        self.assertFalse(copied_folder.owner_id, "Copied folder should not have owner_id set")

        copied_doc = self.company_root_document.with_user(self.document_manager).copy(default={'user_folder_id': 'COMPANY'})
        self.assertTrue(copied_doc)
        self.assertFalse(copied_doc.owner_id, "Copied document should not have owner_id set")

    def test_copy_document_company_to_my_drive(self):
        """
        Manager can copy from company-root folder/doc to My drive.
        Internal user can copy from company-root folder/doc to MY sets owner to that user.
        """
        copied_folder = self.company_root_folder.with_user(self.document_manager).copy(default={'user_folder_id': 'MY'})
        self.assertTrue(copied_folder.owner_id, "Copied folder should have owner_id set")
        self.assertEqual(copied_folder.owner_id.id, self.document_manager.id, "Copied folder owner should be the manager")

        copied_doc = self.company_root_document.with_user(self.document_manager).copy(default={'user_folder_id': 'MY'})
        self.assertTrue(copied_doc.owner_id, "Copied document should have owner_id set")
        self.assertEqual(copied_doc.owner_id.id, self.document_manager.id, "Copied document owner should be the manager")

        copied_folder = self.company_root_folder.with_user(self.doc_user).copy(default={'user_folder_id': 'MY'})
        self.assertTrue(copied_folder.owner_id, "Copied folder should have owner_id set")
        self.assertEqual(copied_folder.owner_id.id, self.doc_user.id, "Copied folder owner should be the internal user")

        copied_doc = self.company_root_document.with_user(self.doc_user).copy(default={'user_folder_id': 'MY'})
        self.assertTrue(copied_doc.owner_id, "Copied document should have owner_id set")
        self.assertEqual(copied_doc.owner_id.id, self.doc_user.id, "Copied document owner should be the internal user")

    def test_copy_document_to_itself(self):
        """ Copying a folder into itself or one of its own descendants raises an UserError. """
        folder = self.company_root_folder
        sub_folder = self.company_sub_folder
        with self.assertRaisesRegex(UserError, "cannot copy a folder into itself"):
            folder.with_user(self.document_manager).copy(default={'user_folder_id': str(folder.id)})

        with self.assertRaisesRegex(UserError, "cannot copy a folder into itself"):
            sub_folder.with_user(self.document_manager).copy(default={'user_folder_id': str(sub_folder.id)})

        with self.assertRaisesRegex(UserError, "cannot copy a folder into itself"):
            folder.with_user(self.document_manager).copy(default={'user_folder_id': str(sub_folder.id)})

    def test_copy_shortcut(self):
        """Check that copying shortcuts works as intended."""
        manager_shortcut = self.document_txt.with_user(self.document_manager).action_create_shortcut()
        self.assertTrue(manager_shortcut.folder_id)
        self.assertEqual(manager_shortcut.copy({'user_folder_id': 'MY'}).user_folder_id, 'MY')
        self.assertEqual(manager_shortcut.copy({'user_folder_id': 'COMPANY'}).user_folder_id, 'COMPANY')
        self.assertEqual(manager_shortcut.copy({'user_folder_id': str(manager_shortcut.folder_id.id)}).user_folder_id,
                         str(manager_shortcut.folder_id.id))

    def test_embedding_actions(self):
        """Check that embedded actions name is translated."""
        self.env['res.lang']._activate_lang('fr_FR')
        doc = self.env['documents.document'].create(
            {'name': 'A request', 'folder_id': self.folder_a.id, 'type': 'request'})
        self.assertFalse(doc.available_embedded_actions_ids)
        self.server_action.with_context(lang='fr_FR').name = "Blablabla"
        self.env['documents.document'].action_folder_embed_action(self.folder_a.id, self.server_action.id)
        doc.invalidate_recordset(['available_embedded_actions_ids'])
        embedded_action = doc.available_embedded_actions_ids
        self.assertEqual(embedded_action.display_name, self.server_action.display_name)
        self.assertEqual(embedded_action.with_context(lang='fr_FR').display_name, "Blablabla")

    def test_embedding_actions_permission(self):
        """Test that embedding actions enforces permissions but allows sudo bypass."""
        user_no_rights = new_test_user(self.env, login='user_no_doc_rights', groups='base.group_user')

        folder = self.env['documents.document'].create({
            'name': 'Test Folder',
            'type': 'folder'
        })
        action = self.env['ir.actions.server'].create({
            'name': 'Test Server Action',
            'model_id': self.env['ir.model']._get('documents.document').id,
            'state': 'code',
        })

        self.env['documents.document'].with_user(user_no_rights).sudo().action_folder_embed_action(folder.id, action.id)
        embedded = self.env['ir.embedded.actions'].search([
            ('action_id', '=', action.id),
            ('parent_res_id', '=', folder.id),
            ('parent_res_model', '=', 'documents.document'),
        ])
        self.assertTrue(embedded, "The action should have been embedded in sudo mode")

        with self.assertRaises(AccessError):
            self.env['documents.document'].with_user(user_no_rights).action_folder_embed_action(folder.id, action.id)
        self.assertTrue(embedded, "The action should not have been unembedded without rights or sudo")

    def test_embedding_actions_obsolescence_gc(self):
        """Actions made children should not be used as embedded actions anymore and are garbage collected."""
        doc = self.env['documents.document'].create({
            'name': 'A request',
            'folder_id': self.folder_a.id,
            'raw': 'test',
        })
        parent_base = self.server_action
        parent_base.group_ids = [Command.create({'name': 'Test Gr', 'user_ids': [Command.link(self.env.user.id)]})]
        child_base = parent_base.copy()
        self.assertTrue(child_base.group_ids)

        self.env['documents.document'].action_folder_embed_action(self.folder_a.id, parent_base.id)
        self.env['documents.document'].action_folder_embed_action(self.folder_a.id, child_base.id)
        self.env['ir.embedded.actions'].with_user(self.env.ref('base.user_root'))._gc_documents_obsolete()
        embedded_action = self.env["ir.embedded.actions"].search([
            ("action_id", "in", (child_base | parent_base).ids)
        ]).grouped(lambda a: a.action_id.id)

        def _visible_action_ids():
            actions = self.env['documents.document'].get_documents_actions(folder_id=self.folder_a.id)
            return {a['id'] for a in actions}

        actions_init = _visible_action_ids()
        self.assertIn(parent_base.id, actions_init)
        self.assertIn(child_base.id, actions_init)

        doc.invalidate_recordset(['available_embedded_actions_ids'])

        parent_base.write({
            'child_ids': [Command.link(child_base.id)],
        })

        actions_before = _visible_action_ids()
        self.assertIn(parent_base.id, actions_before)
        # Child is no longer visible nor embeddable
        self.assertNotIn(child_base.id, actions_before)
        # Even if the record still exists, it cannot be used programmatically either
        self.assertNotIn(child_base.id, doc.available_embedded_actions_ids.action_id.ids)
        doc_in_context = self.env['documents.document'].with_context(
            active_model='documents.document', active_id=doc.id)
        child_embedded = embedded_action[child_base.id].exists()
        self.assertTrue(child_embedded)
        with self.assertRaises(UserError):
            doc_in_context.action_execute_embedded_action(embedded_action[child_base.id].id)
        # Child action gets gc'ed
        self.env['ir.embedded.actions'].with_user(self.ref('base.user_root'))._gc_documents_obsolete()
        self.assertFalse(child_embedded.exists())
        # Not the parent
        doc_in_context.action_execute_embedded_action(embedded_action[parent_base.id].id)

    def test_document_thumbnail_status(self):
        for mimetype in ['application/pdf', 'application/pdf;base64']:
            with self.subTest(mimetype=mimetype):
                pdf_document = self.env['documents.document'].create({
                    'name': 'Test PDF doc',
                    'mimetype': mimetype,
                    'raw': b'%PDF- Fake PDF content',
                    'folder_id': self.folder_b.id,
                })
                self.assertFalse(pdf_document.thumbnail)
                self.assertEqual(pdf_document.thumbnail_status, 'client_generated')

        word_document = self.env['documents.document'].create({
            'name': 'Test DOC doc',
            'mimetype': 'application/msword',
            'folder_id': self.folder_b.id,
        })
        self.assertFalse(word_document.thumbnail)
        self.assertEqual(word_document.thumbnail_status, False)

        webp_document = self.env['documents.document'].create({
            'name': 'Test WEBP doc',
            'mimetype': 'image/webp',
            'raw': WEBP_RAW,
            'folder_id': self.folder_b.id,
        })
        self.assertFalse(webp_document.thumbnail)
        self.assertEqual(webp_document.thumbnail_status, 'client_generated')

        image_documents = self.env['documents.document'].create([{
            'name': 'Test image doc',
            'mimetype': mimetype,
            'raw': GIF_RAW,
            'folder_id': self.folder_b.id,
        } for mimetype in [
            'image/bmp', 'image/gif', 'image/jpeg', 'image/png', 'image/svg+xml', 'image/tiff', 'image/x-icon'
        ]])
        for image_document in image_documents:
            with self.subTest(mimetype=image_document.mimetype):
                self.assertTrue(image_document.thumbnail)
                self.assertEqual(image_document.thumbnail_status, 'present')

        text_documents = self.env['documents.document'].create([{
            'name': 'Test Special Case Text doc',
            'mimetype': mimetype,
            'raw': TEXT_RAW,
            'folder_id': self.folder_b.id,
        } for mimetype in [
            'text/html', 'text/csv', 'text/plain', 'text/javascript', 'text/css', 'text/markdown', 'text/xml',
            'application/json', 'application/xml', 'text/calendar',
        ]])
        for text_document in text_documents:
            with self.subTest(mimetype=text_document.mimetype):
                self.assertFalse(text_document.thumbnail)
                self.assertEqual(text_document.thumbnail_status, False)

    def test_document_max_upload_limit(self):
        Doc = self.env['documents.document']
        ICP = self.env['ir.config_parameter']
        key_doc = 'document.max_fileupload_size'
        key_web = 'web.max_file_upload_size'

        ICP.set_int(key_doc, 20)
        ICP.set_int(key_web, 10)
        self.assertEqual(Doc.get_document_max_upload_limit(), 20)

        ICP.set_int(key_doc, 0)
        self.assertEqual(Doc.get_document_max_upload_limit(), None)

        ICP.search([('key', '=', key_doc)]).unlink()
        self.assertEqual(Doc.get_document_max_upload_limit(), 10)

        ICP.search([('key', '=', key_web)]).unlink()
        self.assertEqual(
            Doc.get_document_max_upload_limit(),
            DEFAULT_MAX_CONTENT_LENGTH,
        )

    def test_document_order_by_is_folder(self):
        # check that the order is "folder first", and then most recent first
        doc_1 = self.env['documents.document'].create([{'name': 'D1', 'raw': 'test'}])
        doc_2 = self.env['documents.document'].create([{'name': 'D2', 'type': 'folder'}])
        doc_3 = self.env['documents.document'].create([{'name': 'D3', 'type': 'url'}])
        doc_4 = self.env['documents.document'].create([{'name': 'D4', 'raw': 'test'}])
        docs = doc_1 | doc_2 | doc_3 | doc_4
        result = self.env['documents.document'].search([('id', 'in', docs.ids)], order='is_folder, create_date DESC, id DESC')

        self.assertEqual(result[0], doc_2)
        self.assertEqual(result[1], doc_4)
        self.assertEqual(result[2], doc_3)
        self.assertEqual(result[3], doc_1)

    def test_document_order_by_last_access_date(self):
        documents = self.env['documents.document'].create([
            {'name': 'D1', 'raw': 'test'},
            {'name': 'D2', 'raw': 'test'},
        ])
        self.env['documents.access'].create([{
            'document_id': documents[0].id,
            'last_access_date': datetime.now() + timedelta(days=1),
            'partner_id': self.env.user.partner_id.id,
        }, {
            'document_id': documents[1].id,
            'last_access_date': datetime.now() + timedelta(days=2),
            'partner_id': self.env.user.partner_id.id,
        }])

        result = self.env['documents.document'].search([('id', 'in', documents.ids)], order='last_access_date_group DESC')
        self.assertEqual(result[0], documents[1])
        self.assertEqual(result[1], documents[0])

        result = self.env['documents.document'].search([('id', 'in', documents.ids)], order='last_access_date_group ASC')
        self.assertEqual(result[0], documents[0])
        self.assertEqual(result[1], documents[1])

    def test_document_group_by_last_access_date(self):
        Doc = self.env['documents.document']
        documents = Doc.create([{'name': f'D{i}', 'raw': 'test'} for i in range(6)])
        self.env['documents.access'].create([{
            'document_id': documents[0].id,
            'last_access_date': datetime.now() - timedelta(hours=1),
            'partner_id': self.env.user.partner_id.id,
        }, {
            'document_id': documents[1].id,
            'last_access_date': datetime.now() - timedelta(days=2),
            'partner_id': self.env.user.partner_id.id,
        }, {
            'document_id': documents[2].id,
            'last_access_date': datetime.now() - timedelta(days=8),
            'partner_id': self.env.user.partner_id.id,
        }, {
            'document_id': documents[3].id,
            'last_access_date': datetime.now() - timedelta(days=40),
            'partner_id': self.env.user.partner_id.id,
        }, {
            'document_id': documents[4].id,
            'last_access_date': datetime.now() - timedelta(minutes=1),
            'partner_id': self.env.user.partner_id.id,
        }, {
            'document_id': documents[5].id,
            'last_access_date': datetime.now() - timedelta(days=1, hours=5),
            'partner_id': self.env.user.partner_id.id,
        }])

        result = Doc.formatted_read_group(
            [('id', 'in', documents.ids)],
            groupby=['last_access_date_group'],
            aggregates=['__count'],
            order='last_access_date_group DESC')

        self.assertEqual(len(result), 4)

        self.assertEqual(result[0]['last_access_date_group'], '3_day')
        self.assertEqual(result[0]['__count'], 2)
        result_day = Doc.search(result[0]['__extra_domain'])
        self.assertEqual(result_day[0], documents[4])
        self.assertEqual(result_day[1], documents[0])
        self.assertEqual(result_day.mapped('last_access_date_group'), ['3_day'] * 2)

        self.assertEqual(result[1]['last_access_date_group'], '2_week')
        self.assertEqual(result[1]['__count'], 2)
        result_week = Doc.search(result[1]['__extra_domain'])
        self.assertEqual(result_week[0], documents[5])
        self.assertEqual(result_week[1], documents[1])
        self.assertEqual(result_week.mapped('last_access_date_group'), ['2_week'] * 2)

        self.assertEqual(result[2]['last_access_date_group'], '1_month')
        self.assertEqual(result[2]['__count'], 1)
        self.assertEqual(Doc.search(result[2]['__extra_domain']), documents[2])
        self.assertEqual(documents[2].last_access_date_group, '1_month')

        self.assertEqual(result[3]['last_access_date_group'], '0_older')
        self.assertEqual(result[3]['__count'], 1)
        self.assertEqual(Doc.search(result[3]['__extra_domain']), documents[3])
        self.assertEqual(documents[3].last_access_date_group, '0_older')

    def test_link_constrains(self):
        folder = self.env['documents.document'].create({'name': 'folder', 'type': 'folder'})
        for url in ("wrong URL format", "https:/ example.com", "test https://example.com"):
            with self.assertRaises(ValidationError):
                self.env['documents.document'].create({
                    'name': 'Test Document',
                    'folder_id': folder.id,
                    'url': url,
                    'type': 'url',
                })

    def test_document_shortcut_to_my_drive(self):
        shortcut_1 = self.document_txt.action_create_shortcut(location_user_folder_id=str(self.folder_b.id))
        shortcut_2 = shortcut_1.with_user(self.internal_user).action_create_shortcut(location_user_folder_id='MY')
        self.assertEqual(shortcut_2.folder_id.id, False)
        self.assertEqual(shortcut_2.with_user(self.internal_user).user_folder_id, 'MY')

    def test_document_upload_from_chatter(self):
        folder = self.env['documents.document'].create([
            {'type': 'folder', 'name': 'folder', 'access_internal': 'view'}
        ])
        attachment = self.env['ir.attachment'].create({
            'raw': GIF_RAW,
            'name': 'TestAttachment.gif',
            'res_model': 'documents.document',
            'res_id': folder.id,
        })
        self.assertNotEqual(attachment.name, folder.name, 'the folder name should not change')

    def test_document_toggle_favorited(self):
        """ Test toggle favorite """
        all_docs = self.document_gif | self.document_txt
        all_docs_user = all_docs.with_user(self.doc_user)
        all_docs_manager = all_docs.with_user(self.document_manager)
        self.assertEqual(all_docs_manager.mapped('is_favorited'), [False, False])
        self.assertEqual(all_docs_user.mapped('is_favorited'), [False, False])

        self.document_gif.with_user(self.document_manager).toggle_favorited()
        all_docs.invalidate_recordset(['is_favorited'])
        self.assertEqual(all_docs_manager.mapped('is_favorited'), [True, False])
        self.assertEqual(all_docs_user.mapped('is_favorited'), [False, False])

        self.document_gif.with_user(self.doc_user).toggle_favorited()
        all_docs.invalidate_recordset(['is_favorited'])
        self.assertEqual(all_docs_user.mapped('is_favorited'), [True, False])

        # Different values: set True for all
        all_docs_user.toggle_favorited()
        all_docs.invalidate_recordset(['is_favorited'])
        self.assertEqual(all_docs_user.mapped('is_favorited'), [True, True])

        # Same values -> toggle all (True -> False)
        all_docs_user.toggle_favorited()
        all_docs.invalidate_recordset(['is_favorited'])
        self.assertEqual(all_docs_user.mapped('is_favorited'), [False, False])

        # Same values -> toggle all (False -> True)
        all_docs_user.toggle_favorited()
        all_docs.invalidate_recordset(['is_favorited'])
        self.assertEqual(all_docs_user.mapped('is_favorited'), [True, True])

    def test_document_toggle_lock(self):
        """ Test unlocking of the documents when the user_permission is set to edit. """

        self.document_txt.write({'owner_id': self.document_manager.id})
        self.document_txt.access_ids.filtered('role').unlink()

        self.document_txt.with_user(self.document_manager).toggle_lock()
        with self.assertRaises(AccessError):
            self.document_txt.with_user(self.doc_user).toggle_lock()
        self.assertEqual(self.document_txt.lock_uid.id, self.document_manager.id, 'viewer should not have unlocked')

        self.document_txt.access_internal = 'edit'
        self.document_txt.with_user(self.doc_user).toggle_lock()
        self.assertFalse(self.document_txt.lock_uid, 'editor should have unlocked')

    def test_res_name_recompute_with_deleted_record(self):
        partner = self.env['res.partner'].create({'name': 'Test Partner'})
        doc = self.env['documents.document'].create({
            'name': 'Test',
            'res_id': partner.id,
            'res_model': 'res.partner',
            'type': 'request',
        })
        self.assertEqual(doc.res_name, "Test Partner")
        partner.unlink()
        self.assertTrue(doc.exists())
        self.assertFalse(doc.res_name)

    @users('dtdm')
    def test_is_protected_admin(self):
        """Test that root folder are not protected for admin."""
        company_root_folder = self.company_root_folder.with_env(self.env)
        company_sub_folder = self.company_sub_folder.with_env(self.env)
        document_company_root = self.document_company_root.with_env(self.env)
        self.assertFalse(company_root_folder.is_protected)
        self.assertFalse(company_sub_folder.is_protected)
        self.assertFalse(document_company_root.is_protected)
        not_protected_documents = self.env['documents.document'].search([('is_protected', '!=', True)])
        self.assertTrue(all(folder in not_protected_documents
                            for folder in company_root_folder | company_sub_folder | document_company_root))

    @users('internal_user')
    def test_is_protected_internal_user(self):
        """Test that root folder are protected for internal user."""
        company_root_folder = self.company_root_folder.with_env(self.env)
        company_sub_folder = self.company_sub_folder.with_env(self.env)
        document_company_root = self.document_company_root.with_env(self.env)
        self.assertTrue(company_root_folder.is_protected,
                        "Folders at the root of Company can only be edited by Documents Managers.")
        self.assertFalse(company_sub_folder.is_protected)
        self.assertFalse(document_company_root.is_protected)
        self.assertIn(company_root_folder,
                      self.env['documents.document'].search([('is_protected', '=', True)]))
        self.assertNotIn(company_sub_folder, self.env['documents.document'].search([('is_protected', '=', True)]))
        self.assertIn(document_company_root, self.env['documents.document'].search([('is_protected', '!=', True)]),
                      "Non folders are never protected")

    @users('documents@example.com')
    def test_create_document_write_other_document_access_ids(self):
        """Test that we cannot write access ids of document by creating another document."""
        inaccessible_document = self.env['documents.document'].with_user(self.internal_user).sudo().create(
            {'type': 'binary', 'raw': b'test'}).with_env(self.env)
        self.assertEqual(inaccessible_document.user_permission, 'none')
        expiration_date = fields.Datetime.add(fields.Datetime.today(), days=10)
        document = self.env['documents.document'].create({
            'type': 'binary', 'raw': b'test', 'name': 'test.txt',
            'folder_id': self.folder_b.id,
            'access_ids': [Command.create({
                'document_id': inaccessible_document.id, 'partner_id': self.doc_user.partner_id.id,
                'role': 'edit', 'expiration_date': expiration_date})],
        })
        access_ids = document.sudo().access_ids.filtered(lambda a: a.expiration_date == expiration_date)
        self.assertEqual(len(access_ids), 1)
        self.assertEqual(access_ids.document_id, document,
                         'The access id created has been redirected to the created document.')
        self.assertEqual(inaccessible_document.user_permission, 'none',
                         'The inaccessible document permissions have not been altered.')
        inaccessible_document.sudo().action_update_access_rights(partners={self.doc_user.partner_id: ('view', False)})
        self.assertEqual(inaccessible_document.user_permission, 'view')
