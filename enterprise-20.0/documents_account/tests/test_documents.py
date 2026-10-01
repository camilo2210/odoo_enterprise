import base64
import textwrap
from datetime import timedelta
from freezegun import freeze_time
from itertools import product
from unittest.mock import patch

from odoo import Command
from odoo.addons.documents_account.tests.common import DocumentsAccountTestCommon, TEXT_RAW, PDF_RAW
from odoo.exceptions import UserError
from odoo.tests.common import tagged, RecordCapturer
from odoo.addons.account.tests.test_account_move_send import TestAccountMoveSendCommon
from odoo.addons.documents.models.documents_document import DocumentsDocument
from odoo.tests.common import HttpCase
from odoo.tools.misc import file_open


@tagged('test_document_bridge')
class TestCaseDocumentsBridgeAccount(DocumentsAccountTestCommon, HttpCase):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bank_journal = cls.company_data['default_journal_bank']
        cls.bank_statement = cls.env['account.bank.statement'].with_context(skip_check_amounts_currencies=True).create({
            'name': 'test_statement',
            'line_ids': [
                (0, 0, {
                    'date': '2019-01-01',
                    'payment_ref': "Happy new year",
                    'amount': 0.0,
                    'journal_id': bank_journal.id,
                }),
            ],
        })
        cls.bank_stmt_folder = cls.env['documents.document'].create({'name': 'folder_stmt', 'type': 'folder'})
        cls.bank_stmt_setting = cls.setup_sync_journal_folder(cls.bank_statement.journal_id, cls.bank_stmt_folder)
        cls.empty_bank_statement = cls.env['account.bank.statement'].create({'name': 'empty'})

    def assertBankStatementDocuments(self, documents):
        """Check the document synchronized from a bank statement attachment."""
        for document in documents:
            self.assertTrue(document.active)
            self.assertEqual(document.folder_id, self.bank_stmt_setting.folder_id)
            self.assertFalse(document.partner_id)
            self.assertEqual(document.owner_id, self.bank_statement.create_uid)
            self.assertEqual(document.tag_ids, self.bank_stmt_setting.tag_ids)

    def test_bridge_bank_statement_create(self):
        """Test document synchronization (at attachment creation) for PDF attachments linked to a bank statement."""
        mimetype_pdf = 'application/pdf'
        self.assertTrue(self.bank_statement.journal_id)

        # Add documents in the chatter
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            # Simulate attachment added in the chatter
            attachments = self.env['ir.attachment'].create([{
                'name': name, 'mimetype': mimetype, 'raw': PDF_RAW if mimetype == mimetype_pdf else TEXT_RAW,
                'res_model': 'account.bank.statement', 'res_id': self.bank_statement.id
            } for name, mimetype in (('t1.pdf', mimetype_pdf), ('t2.pdf', mimetype_pdf), ('t3.txt', 'text/plain'))])
            attachments._post_add_create()
        doc = doc_capturer.records.filtered(lambda d: d.attachment_id in attachments)
        self.assertEqual(doc.mapped('mimetype'), [mimetype_pdf] * 2, "All pdfs are synchronized")
        self.assertEqual(self.bank_statement.message_main_attachment_id, attachments[0])
        self.assertBankStatementDocuments(doc)
        doc_attachment_ids = doc.attachment_id
        self.assertEqual(set(doc.mapped('access_internal')), {"none"},
                         "Rights are inherited from the bank statement folder, no extra rights.")
        self.assertFalse(
            doc.access_ids.filtered(lambda a: a.partner_id != a.document_id.owner_id.partner_id),
            "Rights are inherited from the bank statement folder, no extra rights beside for the owner.")

        # Modify the main attachment
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments[1].register_as_main_attachment()
        self.assertFalse(doc_capturer.records, "No document created")
        self.assertEqual(doc.attachment_id, doc_attachment_ids, "Document attachment not modified")

        # If the journal_id is not configured, no documents are created
        self.assertFalse(self.empty_bank_statement.journal_id)
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments = self.env['ir.attachment'].create([{
                'name': name, 'mimetype': mimetype,
                'res_model': 'account.bank.statement', 'res_id': self.empty_bank_statement.id
            } for name, mimetype in (('t1.pdf', mimetype_pdf), ('t2.pdf', mimetype_pdf), ('t3.txt', 'text/plain'))])
            attachments._post_add_create()
        self.assertFalse(doc_capturer.records.filtered(lambda d: d.attachment_id in attachments),
                         "No document created as journal_id is False")

    def test_bridge_bank_statement_write(self):
        """Test document synchronization (at attachment update) for PDF attachments linked to a bank statement."""
        mimetype_pdf = 'application/pdf'
        self.assertTrue(self.bank_statement.journal_id)

        # Simulate an upload of an attachment and a link to a bank statement afterward
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments = self.env['ir.attachment'].create([
                {'name': name, 'mimetype': mimetype, 'raw': PDF_RAW if mimetype == mimetype_pdf else TEXT_RAW}
                for name, mimetype in (('t1.pdf', mimetype_pdf), ('t2.pdf', mimetype_pdf), ('t3.txt', 'text/plain'))])
        self.assertFalse(doc_capturer.records)
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments.write({'res_model': 'account.bank.statement', 'res_id': self.bank_statement.id})
        doc = doc_capturer.records.filtered(lambda d: d.attachment_id in attachments)
        self.assertEqual(doc.mapped('mimetype'), [mimetype_pdf] * 2, "All pdfs are synchronized")
        self.assertBankStatementDocuments(doc)

        # Rewrite res_model, res_id doesn't duplicate the documents but update them
        new_bank_stmt_folder = self.env['documents.document'].create({'name': 'folder_stmt2', 'type': 'folder'})
        self.bank_stmt_setting = self.setup_sync_journal_folder(self.bank_statement.journal_id, new_bank_stmt_folder)
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments.write({'res_model': 'account.bank.statement', 'res_id': self.bank_statement.id})
        self.assertFalse(doc_capturer.records)
        self.assertEqual(doc.mapped('folder_id'), new_bank_stmt_folder)
        self.assertBankStatementDocuments(doc)

        # Modify a linked attachment
        new2_bank_stmt_folder = self.env['documents.document'].create({'name': 'folder_stmt3', 'type': 'folder'})
        self.bank_stmt_setting = self.setup_sync_journal_folder(self.bank_statement.journal_id, new2_bank_stmt_folder)
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments[0].name = 't1-mod.pdf'
        self.assertFalse(doc_capturer.records, "No document created")
        self.assertEqual(doc.mapped('folder_id'), new_bank_stmt_folder, "Folder unchanged as res_model not written")

        # If the journal_id is not configured, no documents are created
        self.assertFalse(self.empty_bank_statement.journal_id)
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments = self.env['ir.attachment'].create([
                {'name': name, 'mimetype': mimetype}
                for name, mimetype in (('t1.pdf', mimetype_pdf), ('t2.pdf', mimetype_pdf), ('t3.txt', 'text/plain'))])
        self.assertFalse(doc_capturer.records)
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            attachments.write({'res_model': 'account.bank.statement', 'res_id': self.empty_bank_statement.id})
        self.assertFalse(doc_capturer.records.filtered(lambda d: d.attachment_id in attachments),
                         "No document created as journal_id is False")

    def test_bridge_journal_change_journal_updates_tags(self):
        """Test that changing the journal on an account move updates the document tags correctly."""
        tag_shared, tag_j1, tag_j2 = self.env['documents.tag'].create([
            {'name': 'Test Shared Tag'},
            {'name': 'Test Unique J1'},
            {'name': 'Test Unique J2'},
        ])

        folder = self.env['documents.document'].create({'name': 'Purchases Folder', 'type': 'folder'})

        journal_1, journal_2 = self.env['account.journal'].create([{
            'name': f'Purchase Journal {i}',
            'type': 'purchase',
            'code': f'PJ{i}',
        } for i in (1, 2)])

        self.setup_sync_journal_folder(journal_1, folder).tag_ids = tag_shared + tag_j1
        self.setup_sync_journal_folder(journal_2, folder).tag_ids = tag_shared + tag_j2

        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': journal_1.id,
        })
        attachment = self.env['ir.attachment'].create({
            'name': 'vendor_bill.pdf',
            'mimetype': 'application/pdf',
            'raw': PDF_RAW,
            'res_model': 'account.move',
            'res_id': invoice.id,
        })
        attachment.register_as_main_attachment()

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)], limit=1)
        self.assertTrue(document)
        self.assertEqual(document.tag_ids, tag_shared + tag_j1)

        invoice.write({'journal_id': journal_2.id})
        self.assertEqual(document.tag_ids, tag_shared + tag_j2)

    def test_action_view_documents_account_move(self):
        """
        Test the behavior of opening default folder when there are more than one documents.
        """
        account_move_test_1, account_move_test_2 = self.env['account.move'].create([{
            'name': 'Journal Entry 1',
            'move_type': 'entry',
        }, {
            'name': 'Journal Entry 2',
            'move_type': 'entry',
        }])
        self.setup_sync_journal_folder(account_move_test_1.journal_id, self.folder_a)
        self.assertFalse(account_move_test_1.has_documents, "Should be False because no attachment is attached to this record")
        self.assertFalse(account_move_test_2.has_documents, "Should be False because no attachment is attached to this record")
        attachments = self.env['ir.attachment'].create([{
            'name': 'fileText_test.txt',
            'res_model': 'account.move',
            'res_id': account_move_test_1.id,
        }, {
            'name': 'fileText_test2.txt',
            'res_model': 'account.move',
            'res_id': account_move_test_1.id,
        }])
        self.assertTrue(account_move_test_1.has_documents, "Should be True because attachment is attached to this record")
        self.assertFalse(account_move_test_2.has_documents, "Should be False because no attachment is attached to this record")

        # If both the documents have same folder, open that folder.
        action = account_move_test_1.action_view_documents_account_move()
        self.assertEqual(action['context']['searchpanel_default_user_folder_id'], str(self.folder_a.id), "The 'folder A' should be the default.")

        # If both the documents have different folder, open the 'All' folder.
        folder_test = self.env['documents.document'].create({'name': 'folder_test', 'type': 'folder'})
        document = self.env['documents.document'].search([('attachment_id', '=', attachments[0].id)])
        document.folder_id = folder_test.id

        action = account_move_test_1.action_view_documents_account_move()
        self.assertFalse(action['context']['searchpanel_default_user_folder_id'], "The 'All' folder should be the default.")

    def test_bridge_folder_workflow(self):
        """
        tests the create new business model (vendor bill & credit note).

        """
        self.assertFalse(self.document_txt.res_model, "failed at default res model")
        account_moves_count_pre = self.env['account.move'].sudo().search_count([])
        multi_return = (self.document_txt | self.document_gif).account_create_account_move('in_invoice')
        account_moves_count_post = self.env['account.move'].sudo().search_count([])
        self.assertEqual(account_moves_count_post - account_moves_count_pre, 2)
        self.assertEqual(multi_return.get('type'), 'ir.actions.act_window',
                         'failed at invoice workflow return value type')
        self.assertEqual(multi_return.get('res_model'), 'account.move',
                         'failed at invoice workflow return value res model')

        self.assertEqual(self.document_txt.res_model, 'account.move', "failed at workflow_bridge_dms_account"
                                                                           " new res_model")
        vendor_bill_txt = self.env['account.move'].search([('id', '=', self.document_txt.res_id)])
        self.assertTrue(vendor_bill_txt.exists(), 'failed at workflow_bridge_dms_account vendor_bill')
        self.assertEqual(self.document_txt.res_id, vendor_bill_txt.id, "failed at workflow_bridge_dms_account res_id")
        self.assertEqual(vendor_bill_txt.move_type, 'in_invoice', "failed at workflow_bridge_dms_account vendor_bill type")
        vendor_bill_gif = self.env['account.move'].search([('id', '=', self.document_gif.res_id)])
        self.assertEqual(self.document_gif.res_id, vendor_bill_gif.id, "failed at workflow_bridge_dms_account res_id")
        account_moves_count_pre = self.env['account.move'].sudo().search_count([])
        single_return = self.document_txt.account_create_account_move('in_invoice')
        account_moves_count_post = self.env['account.move'].sudo().search_count([])
        self.assertEqual(account_moves_count_post - account_moves_count_pre, 0)
        self.assertEqual(single_return.get('res_model'), 'account.move',
                         'failed at invoice res_model action from workflow create model')
        invoice = self.env[single_return['res_model']].browse(single_return.get('res_id'))
        attachments = self.env['ir.attachment'].search([('res_model', '=', 'account.move'), ('res_id', '=', invoice.id)])
        self.assertEqual(len(attachments), 1, 'there should only be one ir attachment matching')

    def test_bridge_account_account_settings_on_write(self):
        """
        Makes sure the settings apply their values when an ir_attachment is set as message_main_attachment_id
        on invoices.
        """
        folder_test = self.env['documents.document'].create({'name': 'folder_test', 'type': 'folder'})

        for invoice_type in ['in_invoice', 'out_invoice', 'in_refund', 'out_refund', 'entry']:
            invoice_test = self.env['account.move'].with_context(default_move_type=invoice_type).create({
                'name': 'invoice_test',
                'move_type': invoice_type,
            })
            setting = self.setup_sync_journal_folder(invoice_test.journal_id, folder_test)

            attachments = self.env["ir.attachment"]
            for i in range(3):
                attachment = self.env["ir.attachment"].create({
                    "raw": TEXT_RAW,
                    "name": f"fileText_test{i}.txt",
                    "mimetype": "text/plain",
                    "res_model": "account.move",
                    "res_id": invoice_test.id,
                })
                attachment.register_as_main_attachment(force=False)
                attachments |= attachment

            document = self.env["documents.document"].search(
                [("attachment_id", "=", attachments[0].id)]
            )
            self.assertEqual(
                document.folder_id, folder_test, "the text test document have a folder"
            )

            def check_main_attachment_and_document(
                main_attachment, doc_attachment, previous_attachment_ids
            ):
                self.assertRecordValues(
                    invoice_test,
                    [{"message_main_attachment_id": main_attachment.id}],
                )
                self.env["documents.document"].flush_model()
                if invoice_test.move_type == "entry":
                    expected = {
                        "attachment_id": attachments[0].id,
                        "previous_attachment_ids": [],
                    }
                else:
                    expected = {
                        "attachment_id": doc_attachment.id,
                        "previous_attachment_ids": previous_attachment_ids,
                    }
                self.assertRecordValues(document, [expected])

            # Ensure the main attachment is the first one and ensure the document is correctly linked
            check_main_attachment_and_document(attachments[0], attachments[0], [])

            # Switch the main attachment to the second one and ensure the document is updated correctly
            invoice_test.write({"message_main_attachment_id": attachments[1].id})
            check_main_attachment_and_document(
                attachments[1], attachments[1], attachments[0].ids
            )

            # Switch the main attachment to the third one and ensure the document is updated correctly
            attachments[2].register_as_main_attachment(force=True)
            check_main_attachment_and_document(
                attachments[2], attachments[2], (attachments[0] + attachments[1]).ids
            )

            # Ensure all attachments are still linked to the invoice
            attachments = self.env["ir.attachment"].search(
                [("res_model", "=", "account.move"), ("res_id", "=", invoice_test.id)]
            )
            self.assertEqual(
                len(attachments),
                3,
                "there should be 3 attachments linked to the invoice",
            )

            # deleting the setting to prevent duplicate settings.
            setting.unlink()

    def test_bridge_account_account_settings_on_write_with_versioning(self):
        """
        With accounting-document centralization activated, make sure that the right attachment
        is set as main attachment on the invoice when versioning is involved and only one document
        is being created and updated.
        """
        folder_test = self.env["documents.document"].create({"name": "folder_test", "type": "folder"})

        invoice_test = (
            self.env["account.move"]
            .with_context(default_move_type="in_invoice")
            .create({
                "name": "invoice_test",
                "move_type": "in_invoice",
            })
        )

        self.setup_sync_journal_folder(invoice_test.journal_id, folder_test)

        attachments = self.env["ir.attachment"]
        for i in range(1, 3):
            attachment = self.env["ir.attachment"].create({
                "raw": TEXT_RAW,
                "name": f"attachment-{i}.txt",
                "mimetype": "text/plain",
                "res_model": "account.move",
                "res_id": invoice_test.id,
            })
            attachment.register_as_main_attachment(force=False)
            attachments |= attachment

        first_attachment, second_attachment = attachments[0], attachments[1]

        document = self.env["documents.document"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", invoice_test.id)]
        )
        self.assertEqual(
            len(document), 1, "there should be 1 document linked to the invoice"
        )
        self.assertEqual(
            document.folder_id, folder_test, "the text test document have a folder"
        )

        def check_main_attachment_and_document(
            main_attachment, doc_attachment, previous_attachment_ids
        ):
            self.assertRecordValues(
                invoice_test,
                [{"message_main_attachment_id": main_attachment.id}],
            )
            self.assertRecordValues(
                document,
                [
                    {
                        "attachment_id": doc_attachment.id,
                        "previous_attachment_ids": previous_attachment_ids,
                    }
                ],
            )

        # Ensure the main attachment is attachment-1
        check_main_attachment_and_document(first_attachment, first_attachment, [])

        # Version the main attachment:
        # attachment-1 become attachment-3
        # version attachement become attachment-1
        document.write({
            "raw": TEXT_RAW,
            "name": "attachment-3.txt",
            "mimetype": "text/plain",
        })
        third_attachment = document.attachment_id
        first_attachment = document.previous_attachment_ids[0]
        check_main_attachment_and_document(
            third_attachment, third_attachment, first_attachment.ids
        )

        # Switch main attachment to attachment-2
        second_attachment.register_as_main_attachment(force=True)
        check_main_attachment_and_document(
            second_attachment,
            second_attachment,
            (first_attachment + third_attachment).ids,
        )

        # restore versioned attachment (attachment-1)
        document.write({"attachment_id": document.previous_attachment_ids[0].id})
        check_main_attachment_and_document(
            second_attachment,
            first_attachment,
            (third_attachment + second_attachment).ids,
        )

        # Switch main attachment to attachment-3
        third_attachment.register_as_main_attachment(force=True)
        check_main_attachment_and_document(
            third_attachment,
            third_attachment,
            (second_attachment + first_attachment).ids,
        )

        # Ensure there is still only one document linked to the invoice
        document = self.env["documents.document"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", invoice_test.id)]
        )
        self.assertEqual(
            len(document), 1, "there should be 1 document linked to the invoice"
        )

    def test_journal_entry(self):
        """
        Makes sure the settings apply their values when an ir_attachment is set as message_main_attachment_id
        on invoices.
        """
        folder_test = self.env['documents.document'].create({'name': 'Bills', 'type': 'folder'})

        invoice_test = self.env['account.move'].with_context(default_move_type='entry').create({
            'name': 'Journal Entry',
            'move_type': 'entry',
        })
        setting = self.setup_sync_journal_folder(invoice_test.journal_id, folder_test)
        attachments = self.env['ir.attachment'].create([{
            'raw': TEXT_RAW,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': 'account.move',
            'res_id': invoice_test.id
        }, {
            'raw': TEXT_RAW,
            'name': 'fileText_test2.txt',
            'mimetype': 'text/plain',
            'res_model': 'account.move',
            'res_id': invoice_test.id
        }])
        documents = self.env['documents.document'].search([('attachment_id', 'in', attachments.ids)])
        self.assertEqual(len(documents), 2)
        setting.unlink()

    def test_bridge_account_sync_partner(self):
        """
        Tests that the partner is always synced on the document, regardless of settings
        """
        partner_1, partner_2 = self.env['res.partner'].create([{'name': 'partner_1'}, {'name': 'partner_2'}])
        self.document_txt.partner_id = partner_1
        (self.document_txt | self.document_gif).account_create_account_move('in_invoice')
        move = self.env['account.move'].browse(self.document_txt.res_id)
        self.assertEqual(move.partner_id, partner_1)
        move.partner_id = partner_2
        self.assertEqual(self.document_txt.partner_id, partner_2)

    def test_embedded_pdf(self):
        document = self.env['documents.document'].create({
            'name': 'test',
            'folder_id': self.folder_a.id,
            'raw': b'<?xml version="1.0" ?>\n<test> </test>',
        })
        self.assertEqual(document.mimetype, 'text/xml')
        self.assertFalse(document._extract_pdf_from_xml())
        self.assertFalse(document.thumbnail_status)
        self.assertFalse(document.has_embedded_pdf)

        document = self.env['documents.document'].create({
            'name': 'test',
            'folder_id': self.folder_a.id,
            'raw': b'<?xml version="1.0" ?>\n<test> <Attachment>JVBERi0gRmFrZSBQREYgY29udGVudA==</Attachment> </test>',
        })
        self.assertEqual(document.mimetype, 'text/xml')
        self.assertEqual(document._extract_pdf_from_xml(), b'%PDF- Fake PDF content')
        self.assertEqual(document.thumbnail_status, 'client_generated')
        self.assertTrue(document.has_embedded_pdf)

    def test_pdf_first_page_route_for_embedded_pdf(self):
        with file_open("documents_account/tests/assets/vendor_bill_example.xml", "rb") as xml_file:
            xml_bytes = xml_file.read()

        document = self.env['documents.document'].create({
            'name': 'test',
            'folder_id': self.folder_a.id,
            'raw': base64.b64encode(xml_bytes).decode(),
        })

        self.assertEqual(document.mimetype, "text/xml")
        self.assertTrue(document.has_embedded_pdf)
        self.assertTrue(document._extract_pdf_from_xml())
        self.assertEqual(document.thumbnail_status, 'client_generated')

        self.authenticate("admin", "admin")
        pdf_first_page = self.url_open(f'/documents/content/pdf_first_page/{document.access_token}')
        self.assertEqual(pdf_first_page.status_code, 200)

    def test_tour_embedded_pdf_thumbnail_generation(self):
        self.start_tour("/odoo", "test_embedded_pdf_thumbnail_generation", login="admin")

    def test_move_document_unlink(self):
        """Test that the document is sent to trash when the `account.move` is unlinked."""
        document1, document2 = documents = self.document_txt | self.document_gif
        documents.account_create_account_move('in_invoice')
        self.assertEqual(document1.res_model, "account.move")
        self.assertEqual(document2.res_model, "account.move")
        move1 = self.env["account.move"].browse(document1.res_id).exists()
        move2 = self.env["account.move"].browse(document2.res_id).exists()
        self.assertTrue(move1)
        self.assertTrue(move2)
        attachment1 = self.env['ir.attachment'].search([
            ('res_model', '=', move1._name),
            ('res_id', '=', move1.id),
        ])
        attachment2 = self.env['ir.attachment'].search([
            ('res_model', '=', move2._name),
            ('res_id', '=', move2.id),
        ])
        # attachment not linked to a document
        attachment3 = self.env['ir.attachment'].create({
            'name': 'Attachment 3',
            'res_model': move2._name,
            'res_id': move2.id,
        })
        self.assertEqual(len(attachment1), 1)
        self.assertEqual(len(attachment2), 1)
        self.assertEqual(attachment1 | attachment2, documents.attachment_id)
        attachments_checksum = documents.attachment_id.mapped('checksum')

        self.env.flush_all()
        (move1 | move2).unlink()

        self.assertTrue(document1.exists())
        self.assertTrue(document1.attachment_id.exists())
        self.assertFalse(document1.active)

        self.assertTrue(document2.exists())
        self.assertTrue(document2.attachment_id.exists())
        self.assertFalse(document2.active)

        self.assertFalse((attachment1 | attachment2).exists(), "The attachments have been deleted")
        self.assertEqual(documents.attachment_id.mapped('checksum'), attachments_checksum,
                         "The attachments have been copied before being deleted and reassociated with the documents")

        self.assertFalse(attachment3.exists(),
            "That attachment is not linked to a record and so it should be removed")

        # removing the document in the trash clean the attachment
        document2.unlink()
        self.assertFalse(attachment2.exists())

    def test_workflow_create_misc_entry(self):
        misc_entry_action = (self.document_txt | self.document_gif).account_create_account_move('entry')
        move = self.env['account.move'].browse(self.document_txt.res_id)
        self.assertEqual(misc_entry_action.get('res_model'), 'account.move')
        self.assertEqual(move.move_type, 'entry')

    def test_workflow_create_bank_statement_raise_content_parsing(self):
        for document in self.document_txt, self.document_gif:
            with self.subTest(document=document.name):
                with self.assertRaises(UserError) as err:
                    document.account_create_account_bank_statement()
                self.assertEqual(
                    err.exception.args[0],
                    f"All or part of the following file(s) could not be imported:\n"
                    f"- {document.name}: Could not make sense of the given file.\n"
                    f"Did you install the module to support this type of file?",
                )

    def test_workflow_create_bank_statement_raise_no_journal(self):
        new_company = self.env['res.company'].create({'name': 'new_company_without_journals'})
        doc_in_new_company = self.document_txt.copy({'company_id': new_company.id})

        for sudo in False, True:
            # Running test with sudo similulates server actions that run with sudo rights
            with self.subTest(sudo=sudo):
                with self.assertRaises(UserError) as err:
                    doc_in_new_company.with_company(new_company).sudo(sudo).account_create_account_bank_statement()
                self.assertEqual(
                    err.exception.args[0],
                    "No journal could be found in company new_company_without_journals for any of those types: bank",
                )

    def test_workflow_create_vendor_bill(self):
        vendor_bill_entry_action = self.document_txt.account_create_account_move('in_invoice')
        move = self.env['account.move'].browse(self.document_txt.res_id)
        self.assertEqual(vendor_bill_entry_action.get('res_model'), 'account.move')
        self.assertEqual(move.move_type, 'in_invoice')

    def test_workflow_create_vendor_receipt(self):
        # Activate the group for the vendor receipt
        vendor_receipt_action = self.document_txt.account_create_account_move('in_receipt')
        move = self.env['account.move'].browse(self.document_txt.res_id)
        self.assertEqual(vendor_receipt_action.get('res_model'), 'account.move')
        self.assertEqual(move.move_type, 'in_receipt')

    def test_documents_xml_attachment(self):
        """ Tests that XML and PDF attachments are correctly synced as documents,
        whether they are linked to the move during create() or write().
        """
        folder_test = self.env['documents.document'].create({'name': 'Bills', 'type': 'folder'})

        invoice = self.init_invoice('out_invoice', amounts=[1000], post=True)
        self.setup_sync_journal_folder(invoice.journal_id, folder_test)

        expected_sync_att_ids = []

        for fmt, no_doc in product(('application/xml', 'text/xml', 'application/txt'), (False, True)):
            expected_doc_count = 0 if fmt == 'application/txt' or no_doc else 1
            folder_domain = [('folder_id', '=', folder_test.id)] if expected_doc_count else []
            fmt_name = fmt.replace('/', '_')

            # 1. Test sync via attachment.create()
            create_att = self.env['ir.attachment'].with_context(no_document=no_doc).create({
                'raw': b'<text/>',
                'name': f'create-{fmt_name}.txt',
                'mimetype': fmt,
                'res_model': 'account.move',
                'res_id': invoice.id,
            })
            self.assertEqual(
                self.env['documents.document'].search_count([('attachment_id', '=', create_att.id)] + folder_domain),
                expected_doc_count,
                f"{fmt} failed correct sync behavior on create() with no_documents={no_doc}"
            )

            # 2. Test sync via attachment.write()
            write_att = self.env['ir.attachment'].create({
                'raw': b'<text/>',
                'name': f'write-{fmt_name}.txt',
                'mimetype': fmt,
            })
            self.assertFalse(self.env['documents.document'].search_count([('attachment_id', '=', write_att.id)]))

            write_att.with_context(no_document=no_doc).write({
                'res_model': 'account.move',
                'res_id': invoice.id,
            })
            self.assertEqual(
                self.env['documents.document'].search_count([('attachment_id', '=', write_att.id)] + folder_domain),
                expected_doc_count,
                f"{fmt} failed correct sync behavior on write() with no_documents={no_doc}"
            )
            if expected_doc_count == 1:
                expected_sync_att_ids.extend([create_att.id, write_att.id])

        # Test PDF sync
        pdf_att = self.env['ir.attachment'].create({
            'raw': PDF_RAW,
            'name': 'file.pdf',
            'mimetype': 'application/pdf',
            'res_model': 'account.move',
            'res_id': invoice.id,
        })
        self.assertFalse(invoice.message_main_attachment_id)
        self.assertFalse(
            self.env['documents.document'].search_count([('attachment_id', '=', pdf_att.id)]),
            "PDF should not be attached if not main attachment",
        )
        pdf_att.register_as_main_attachment(force=True)
        self.assertTrue(
            self.env["documents.document"].search_count([
                ("attachment_id", "=", pdf_att.id),
                ("folder_id", "=", folder_test.id),
            ])
        )
        expected_sync_att_ids.append(pdf_att.id)

        # Test final count of syncs
        all_docs = self.env['documents.document'].search([('attachment_id', 'in', expected_sync_att_ids)])
        self.assertEqual(len(all_docs), len(expected_sync_att_ids), "All XMLs and the registered PDF must be synced")
        self.assertEqual(all_docs.mapped('folder_id'), folder_test, "All documents must be in the synced folder")

    def test_embeddable_server_action_domain(self):
        """Test the domain that filters server actions that can be embedded on a folder.

        Especially that server actions that create a record with a journal of a company
        different from the current one are filtered out.
        """
        IrActionServer = self.env['ir.actions.server']

        def get_server_actions_for_company(company):
            return IrActionServer.with_company(company).search(
                self.env['documents.document'].with_company(company)._get_embeddable_server_action_domain())

        company_1 = self.env.company
        company_2 = self.setup_other_company()['company']
        companies = company_1 | company_2
        pre_existing = {company: get_server_actions_for_company(company) for company in companies}
        action_base_vals = {'model_id': self.env['ir.model']._get_id('documents.document')}
        action_create_base_vals = {
            **action_base_vals,
            'state': 'documents_account_record_create',
            'documents_account_create_model': 'account.move.in_invoice',
        }
        journal_id_per_company = {
            company: self.env['account.move'].with_company(company)._get_suitable_journal_ids('in_invoice').ids[0]
            for company in companies
        }
        for company in companies:
            other_company = companies - company
            action_single_company_vals = {
                **action_create_base_vals,
                'name': f'single {company.name}',
                'documents_account_journal_id': journal_id_per_company[company],
            }
            IrActionServer.with_company(company).create([
                action_single_company_vals,
                {
                    **action_base_vals,
                    'name': f'multi {company.name}',
                    'state': 'multi',
                    'child_ids': [Command.create(action_single_company_vals)],
                },
                {
                    **action_base_vals,
                    'name': 'multi invalid',
                    'state': 'multi',
                    'child_ids': [
                        IrActionServer.with_company(company).create(action_single_company_vals).id,
                        IrActionServer.with_company(other_company).create({
                            **action_single_company_vals,
                            'documents_account_journal_id': journal_id_per_company[other_company]
                        }).id,
                    ],
                }])
        action_single_vals = {
            **action_create_base_vals,
            'name': 'single',
        }
        IrActionServer.create([
            action_single_vals,
            {
                **action_base_vals,
                'name': 'multi',
                'state': 'multi',
                'child_ids': [Command.create(action_single_vals)],
            }])

        self.assertEqual(
            set((get_server_actions_for_company(company_1) - pre_existing[company_1]).mapped('name')),
            {'multi', f'multi {company_1.name}', 'single', f'single {company_1.name}'}
        )
        self.assertEqual(
            set((get_server_actions_for_company(company_2) - pre_existing[company_2]).mapped('name')),
            {'multi', f'multi {company_2.name}', 'single', f'single {company_2.name}'}
        )

    def test_embeddable_actions_gc(self):
        """
        Test that when the Garbage Collector runs it doesn't unlink account embedded actions linked to other companies.
        """
        company_1 = self.env.company
        company_2 = self.setup_other_company()['company']

        model_id = self.env['ir.model']._get_id('documents.document')
        journal_id = self.env['account.move'].with_company(company_2)._get_suitable_journal_ids('in_invoice').ids[0]
        action_company_2 = self.env['ir.actions.server'].with_company(company_2).create({
            'name': 'Company 2 Action',
            'model_id': model_id,
            'state': 'multi',
            'child_ids': [Command.create({
                'name': 'Company 2 Child Action',
                'model_id': model_id,
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
                'documents_account_journal_id': journal_id,
            })]
        })
        self.env['documents.document'].action_folder_embed_action(self.folder_a.id, action_company_2.id)
        embedded_action = self.env['ir.embedded.actions'].search([
            ('action_id', '=', action_company_2.id),
            ('parent_res_id', '=', self.folder_a.id),
            ('parent_res_model', '=', 'documents.document'),
        ])

        self.assertTrue(embedded_action.exists())
        self.env['ir.embedded.actions'].with_company(company_1)._gc_documents_obsolete()
        self.assertTrue(embedded_action.exists(), 'Action should still exist even if different company')

    def test_gc_clear_bin_for_journal_folder(self):
        """Check that account setting folders are excluded from garbage collector."""
        folder_setting, other_folder = self.env['documents.document'].create([
            {'name': 'Folder setting', 'type': 'folder'},
            {'name': 'Other folder', 'type': 'folder'},
        ])
        self.env['documents.account.folder.setting'].search([]).unlink()
        self.setup_sync_journal_folder(self.company_data['default_journal_sale'], folder_setting)
        (folder_setting | other_folder).action_archive()
        document_deletion_date = folder_setting.write_date + timedelta(
            days=folder_setting.get_deletion_delay(), seconds=30)
        with freeze_time(document_deletion_date):
            self.env["documents.document"]._gc_clear_bin()

        self.assertTrue(folder_setting.exists(),
                        "folder linked to journal setting should not be deleted after gc_clear_bin")
        self.assertFalse(other_folder.exists(),
                        "folder not linked to journal setting should be deleted after gc_clear_bin")

    def test_permissions_adding_document_attachment(self):
        """Check that attachment of send_and_print can be copied in composer."""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': '2016-01-01',
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500,
                'tax_ids': [],
            })]
        })
        attachment = self.env['ir.attachment'].create([{
            'name': 'att.pdf',
            'res_id': invoice.id,
            'res_model': 'account.move',
            'res_field': 'invoice_pdf_report_file',  # simulates send & print
            'raw': b'test',
            'type': 'binary',
        }])
        attachment.register_as_main_attachment()

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)], limit=1)
        self.assertTrue(document)
        document.with_user(self.simple_accountman).add_documents_attachment("mail.compose.message", 0)
        attachment_copy = self.env['ir.attachment'].search([('original_id', '=', attachment.id)], limit=1)
        self.assertTrue(attachment_copy)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAccountMoveSendDocument(DocumentsAccountTestCommon, TestAccountMoveSendCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder_test = cls.env['documents.document'].create({'name': 'folder_test', 'type': 'folder'})
        cls.journal = cls.company_data['default_journal_purchase']
        cls.setup_sync_journal_folder(cls.journal, cls.folder_test)

    def test_log_note_and_incoming_email_document_creation(self):
        """
        Test that posting a file via log note or incoming email syncs to Documents ONLY if its mimetype
        is explicitly allowed by `_should_attach_to_record` (e.g., PDFs, CSVs). Unlisted formats (e.g., images)
        are orphaned and must not trigger a document sync.
        """
        test_cases = [
            ('invoice.pdf', 'application/pdf', PDF_RAW, True),
            ('receipt.png', 'image/png', b'dummy image content', False),
        ]
        origins = ('log_note', 'email')
        for origin, (filename, mimetype, content, should_sync) in product(origins, test_cases):
            with self.subTest(origin=origin, filename=filename, mimetype=mimetype):
                if origin == 'log_note':
                    invoice = self.init_invoice("in_invoice", amounts=[1000], post=False)
                    attachment = self.env['ir.attachment'].create({
                        'name': filename,
                        'raw': content,
                        'mimetype': mimetype,
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                    })
                    invoice.message_post(message_type='comment', attachment_ids=attachment.ids)
                elif origin == 'email':
                    email_raw = textwrap.dedent(f"""\
                        MIME-Version: 1.0
                        Date: Fri, 26 Nov 2021 16:27:45 +0100
                        Message-ID: <test-{filename}-{origin}@example.com>
                        Subject: Incoming bill {filename}
                        From: Someone <someone@some.company.com>
                        To: {self.journal.alias_id.display_name}
                        Content-Type: multipart/alternative; boundary="000000000000a47519057e029630"

                        --000000000000a47519057e029630
                        Content-Type: text/plain; charset="UTF-8"

                        Here is your document.

                        --000000000000a47519057e029630
                        Content-Type: {mimetype}
                        Content-Transfer-Encoding: base64
                        Content-Disposition: attachment; filename="{filename}"

                        {base64.b64encode(content).decode()}
                        --000000000000a47519057e029630--
                    """)
                    invoice = self.env['mail.thread'].message_process(
                        'account.move',
                        email_raw,
                        custom_values={'move_type': 'in_invoice', 'journal_id': self.journal.id}
                    )
                    attachment = self.env['ir.attachment'].search([('name', '=', filename)], limit=1)
                    self.assertTrue(attachment)

                self.assertEqual(invoice.message_main_attachment_id, attachment)
                doc = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
                if should_sync:
                    self.assertEqual(attachment.res_model, 'account.move')
                    self.assertTrue(doc)
                else:
                    self.assertFalse(attachment.res_model)
                    self.assertFalse(doc)

    def test_send_and_print_document_creation(self):
        """
        Makes sure the documents are created when attaching pdf and xml to the move
        """
        folder_test = self.env['documents.document'].create({'name': 'Bills', 'type': 'folder'})
        move = self.init_invoice("out_invoice", amounts=[1000], post=True)
        setting = self.setup_sync_journal_folder(move.journal_id, folder_test)

        wizard = self.create_send_and_print(move)
        wizard.action_send_and_print()
        attachments = move.attachment_ids | move.invoice_pdf_report_id
        documents = self.env['documents.document'].search([('attachment_id', 'in', attachments.ids)])
        self.assertEqual(len(documents), len(attachments), "Each move attachment should create a corresponding document")
        with patch.object(DocumentsDocument, '_get_is_multipage', return_value=False):
            setting.unlink()
