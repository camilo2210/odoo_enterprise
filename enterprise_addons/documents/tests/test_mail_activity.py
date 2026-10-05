from odoo.tests.common import tagged

from .test_documents_common import GIF_RAW, TEXT_RAW, TransactionCaseDocuments


@tagged('mail_activity')
class TestDocumentsMailActivity(TransactionCaseDocuments):

    def test_request_activity(self):
        """
        Makes sure the document request activities are working properly
        """
        partner = self.env['res.partner'].create({'name': 'Pepper Street'})
        activity_type = self.env['mail.activity.type'].create({
            'name': 'test_activity_type',
            'category': 'upload_file',
            'folder_id': self.folder_a.id,
        })
        activity = self.env['mail.activity'].create({
            'activity_type_id': activity_type.id,
            'user_id': self.doc_user.id,
            'res_id': partner.id,
            'res_model_id': self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'summary': 'test_summary',
        })

        activity_2 = self.env['mail.activity'].create({
            'activity_type_id': activity_type.id,
            'user_id': self.doc_user.id,
            'res_id': partner.id,
            'res_model_id': self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id,
            'summary': 'test_summary_2',
        })

        attachment = self.env['ir.attachment'].create({
            'raw': GIF_RAW,
            'name': 'Test activity 1',
        })

        document_1 = self.env['documents.document'].search([('request_activity_id', '=', activity.id)], limit=1)
        document_2 = self.env['documents.document'].search([('request_activity_id', '=', activity_2.id)], limit=1)

        self.assertEqual(document_1.type, 'request')
        self.assertEqual(document_2.type, 'request')

        self.assertEqual(document_1.name, 'test_summary', 'the activity document should have the right name')
        self.assertEqual(document_1.folder_id.id, self.folder_a.id, 'the document 1 should have the right folder')
        self.assertEqual(document_2.folder_id.id, self.folder_a.id, 'the document 2 should have the right folder')
        activity._action_done(attachment_ids=[attachment.id])
        document_2.write({'raw': TEXT_RAW, 'name': 'new filename'})
        self.assertEqual(document_1.attachment_id.id, attachment.id,
                         'the document should have the newly added attachment')
        self.assertFalse(activity.active, 'the activity should be done')
        self.assertFalse(activity_2.active, 'the activity_2 should be done')
