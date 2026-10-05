# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase


class testAttachmentAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': "foo",
            'login': "foo",
            'email': "foo@bar.com",
            'group_ids': [(6, 0, [cls.env.ref('documents.group_documents_user').id])]
        })
        folder = cls.env['documents.document'].create({'type': 'folder', 'name': 'foo', 'access_internal': 'edit'})
        cls.document_defaults = {
            'folder_id': folder.id,
        }

    def test_user_document_attachment_without_res_fields(self):
        """Test an employee can create a document linked to an attachment without res_model/res_id"""
        env_user = self.env(user=self.user)
        # As user, create an attachment without res_model/res_id
        attachment = env_user['ir.attachment'].create({'name': 'foo', 'raw': b'foo'})
        # As user, create a document linked to that attachment
        document = env_user['documents.document'].create({'attachment_id': attachment.id, **self.document_defaults})
        # As user, ensure the content of the attachment can be read through the document
        self.assertEqual(document.raw.content, b'foo')
        # As user, create another attachment without res_model/res_id
        attachment_2 = env_user['ir.attachment'].create({'name': 'foo', 'raw': b'bar'})
        # As user, change the attachment of the document to this second attachment
        document.write({'attachment_id': attachment_2.id})
        # As user, ensure the content of this second attachment can be read through the document
        self.assertEqual(document.raw.content, b'bar')

    def test_user_document_attachment_without_res_fields_created_by_admin(self):
        """Test an employee can read the content of the document's attachment created by another user, the admin,
        while the attachment does not have a res_model/res_id
        In documents, there is a special mechanism setting the attachment res_model/res_id on creation of the document
        if the attachment res_model/res_id is not set. However, the same mechanism is not there in `write`.
        So, both cases need to be tested.
        """
        # As admin, create an attachment without res_model/res_id
        attachment = self.env['ir.attachment'].create({'name': 'foo', 'raw': b'foo'})
        # As admin, create a document linked to that attachment
        document = self.env['documents.document'].create({'attachment_id': attachment.id, **self.document_defaults})
        # Ensure the attachment res_model/res_id have been set automatically
        self.assertEqual(attachment.res_model, 'documents.document')
        self.assertEqual(attachment.res_id, document.id)

        # As user, ensure the attachment raw can be read directly and through the document
        self.env.invalidate_all()
        self.assertEqual(attachment.with_user(self.user).raw.content, b'foo')
        # As user, ensure the content of the attachment can be read through the document
        self.assertEqual(document.with_user(self.user).raw.content, b'foo')

        # As admin, create a second attachment without res_model/res_id
        attachment = self.env['ir.attachment'].create({'name': 'bar', 'raw': b'bar'})
        # As admin, link this second attachment to the previously created document (write instead of create)
        document.write({'attachment_id': attachment.id})
        # Mimic the previous behavior before odoo/enterprise#64530,
        # which wasn't correctly setting `res_model` and `res_id` on the attachment
        # upon a `write` of `attachment_id` on `documents.document`
        # to assert Documents users can still read `attachment_raw`
        # for past documents for which `res_model` and `res_id` is not correctly set on the `attachment_id`
        attachment.res_model = attachment.res_id = False
        # Ensure the res_model/res_id has not been set automatically during the write on the document
        self.assertFalse(attachment.res_model)
        self.assertFalse(attachment.res_id)

        # As user ensure the attachment itself cannot be read
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            attachment.with_user(self.user).raw.content
        # But, as user, the content of the attachment can be read through the document
        self.assertEqual(document.with_user(self.user).raw.content, b'bar')

    def test_user_read_unallowed_attachment(self):
        """Test a user cannot access an attachment he is not supposed to through a document"""
        # As admin, create an attachment for which you require the settings group to access
        autovacuum_job = self.env.ref('base.autovacuum_job')
        attachment_forbidden = self.env['ir.attachment'].create({
            'name': 'foo', 'raw': b'foo',
            'res_model': autovacuum_job._name, 'res_id': autovacuum_job.id,
        })
        # As user, make sure this is indeed not possible to access that attachment data directly
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            attachment_forbidden.with_user(self.user).raw
        # As user, create a document pointing to that attachment
        # and make sure it raises an access error
        with self.assertRaises(AccessError):
            document = self.env['documents.document'].with_user(self.user).create({
                'attachment_id': attachment_forbidden.id,
                **self.document_defaults,
            })
            document.raw

        # As user, update the attachment of an existing document to the unallowed attachment
        # and make sure it raises an access error
        attachment_tmp = self.env['ir.attachment'].with_user(self.user).create({
            'name': 'bar', 'raw': b'bar',
        })
        document = self.env['documents.document'].with_user(self.user).create({
            'attachment_id': attachment_tmp.id,
            **self.document_defaults,
        })
        with self.assertRaises(AccessError):
            document.write({'attachment_id': attachment_forbidden.id})
            document.raw

        with self.assertRaises(AccessError):
            self.env["documents.document"].with_user(self.user).onchange(
                {"attachment_id": attachment_forbidden.id},
                ["attachment_id"],
                {"raw": {}},
            )

        with self.assertRaises(AccessError):
            self.env["documents.document"].with_user(self.user).with_context(
                default_attachment_id=attachment_forbidden.id,
            ).onchange(
                {},
                [],
                {"attachment_id": {}, "raw": {}},
            )

        self.env["ir.default"].with_user(self.user).set(
            "documents.document",
            "attachment_id",
            attachment_forbidden.id,
            user_id=True,
        )
        with self.assertRaises(AccessError):
            self.env["documents.document"].with_user(self.user).onchange(
                {},
                [],
                {"attachment_id": {}, "raw": {}},
            )

    def test_create_shortcut(self):
        doc = self.env['documents.document'].create({
            'name': 'secret',
            'access_internal': 'none',
            'raw': 'test',
        })

        with self.assertRaises(AccessError):
            self.env['documents.document'].with_user(self.user).create({'shortcut_document_id': doc.id})
