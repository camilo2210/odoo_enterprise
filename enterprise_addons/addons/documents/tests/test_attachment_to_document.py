from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import TransactionCase, users


class TestAttachmentToDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = mail_new_test_user(
            cls.env,
            login="internal_user",
            name="Internal user",
            groups="base.group_user",
        )
        cls.internal_user_2 = mail_new_test_user(
            cls.env,
            login="internal_user_2",
            name="Internal user 2",
            groups="base.group_user",
        )
        cls.company_sub_folder = cls.env['documents.document'].create({
            'name': 'Company Sub folder',
            'type': 'folder',
            'folder_id': False,
            'access_internal': 'edit',
        })

    @users('internal_user')
    def test_compute_linked_document_id(self):
        file_data = b'This is a test file.'
        document_my_drive, document_company = self.env['documents.document'].create([
            {
                'name': 'Personal Doc',
                'owner_id': self.internal_user.id,
                'folder_id': False,
                'raw': file_data,
            }, {
                'name': 'Company Doc',
                'owner_id': False,
                'folder_id': self.company_sub_folder.id,
                'access_internal': 'view',
                'raw': file_data,
            }])
        self.attachment_id = self.env['ir.attachment'].create({
            'name': 'test attachment',
            'raw': file_data,
        })

        self.assertEqual(document_my_drive.checksum, self.attachment_id.checksum)
        self.assertEqual(document_company.checksum, self.attachment_id.checksum)
        self.assertFalse(self.attachment_id.document_ids)
        self.assertEqual(self.attachment_id.linked_document_id, document_my_drive)
        self.assertEqual(self.attachment_id.with_user(self.internal_user_2).linked_document_id, document_company)
