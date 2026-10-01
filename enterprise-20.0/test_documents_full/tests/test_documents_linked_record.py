from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import new_test_user, users
from odoo.tools import mute_logger

from odoo.addons.test_documents_full.tests.common import TestDocumentsBridgeCommon


class TestDocumentsLinkedRecord(TestDocumentsBridgeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_2 = cls.env["res.company"].create({"name": "Company 2"})
        cls.company_2.documents_bridge_folder_id = cls.bridge_folder_company2 = cls.env["documents.document"].create({
            "name": "Folder Company 2", "type": "folder", "company_id": cls.company_2.id})
        (cls.env.company | cls.company_2).documents_bridge_settings = True
        cls.doc_user = new_test_user(cls.env, 'documents@example.com',
                                     groups='base.group_user,documents.group_documents_user',
                                     company_ids=[Command.set([cls.company.id, cls.company_2.id])])

        cls.companies = cls.company | cls.company_2
        cls.folders = cls.env['documents.document'].create(
            [{'name': f'{company.name}-{idx}', 'type': 'folder', 'company_id': company.id,
              'folder_id': company.documents_bridge_folder_id.id}
             for company in cls.companies for idx in range(2)])
        cls.records = cls.env['documents.mixin.test.folder.per.instance'].create(
            [{'name': folder.name, 'record_folder_id': folder.id, 'company_id': folder.company_id.id}
             for folder in cls.folders])
        cls.other_folder = cls.env['documents.document'].create(
            {'name': 'other folder', 'type': 'folder', 'folder_id': cls.bridge_folder.id, 'company_id': False})
        (cls.bridge_folder | cls.bridge_folder_company2 | cls.other_folder).action_update_access_rights(
            partners={cls.doc_user.partner_id: ('edit', False)})
        cls.records_per_company = cls.records.grouped('company_id')
        cls.folders_per_company = cls.folders.grouped('company_id')

    def test_initial_values(self):
        """Check the initial values and that record folders are initialized on create."""
        self.assertTrue(self.env.company.documents_bridge_settings)
        for folder, record in zip(self.folders, self.records):
            with self.subTest(folder.name):
                self.assertEqual(record['record_folder_id'], folder)
                self.assertEqual(folder.res_model, record._name)
                self.assertEqual(folder.res_id, record.id)
        self.assertFalse(self.other_folder.res_model)
        self.assertFalse(self.other_folder.res_id)
        self.assertEqual(len(self.folders_per_company[self.company]), 2)
        self.assertEqual(len(self.folders_per_company[self.company_2]), 2)
        self.assertEqual(len(self.records_per_company[self.company]), 2)
        self.assertEqual(len(self.records_per_company[self.company_2]), 2)

    @mute_logger('odoo.addons.base.models.ir_access')
    @users('documents@example.com')
    def test_folder_sync_with_record(self):
        """Test record-folder synchronization."""
        Record = self.env['documents.mixin.test.folder.per.instance']
        Document = self.env['documents.document']
        for company in self.companies:
            with self.subTest(company=company.name):
                # Verify that creating a new record with a folder correctly links the folder to the record.
                new_folder, other_folder = Document.create(
                    [{'name': name, 'type': 'folder'} for name in ('new', 'other')])
                new_record = Record.create(
                    {'name': 'new record', 'record_folder_id': new_folder.id, 'company_id': company.id})
                self.assertEqual(new_folder.res_model, new_record._name)
                self.assertEqual(new_folder.res_id, new_record.id)
                self.assertEqual(new_record.record_folder_id, new_folder)

                # Check that changing the record folder update the folder linked record.
                new_record.record_folder_id = other_folder
                self.assertEqual(other_folder.res_model, new_record._name)
                self.assertEqual(other_folder.res_id, new_record.id)
                self.assertEqual(new_folder.res_id, new_record.id, "The folder previouly linked keeps its link.")
                new_record.record_folder_id = new_folder

                # Check folder assignation conflicts
                with self.assertRaises(
                        UserError, msg="The res_model, res_id cannot be cleared on folder linked to a record."):
                    new_folder.write({'res_model': False, 'res_id': False})
                with self.assertRaises(
                        UserError, msg="A folder cannot be shared with another record"):
                    Record.create(
                        {'name': 'new_record2', 'record_folder_id': new_folder.id, 'company_id': company.id})
                new_record2 = Record.create({'name': 'new_record2', 'company_id': company.id})
                with self.assertRaises(
                        UserError, msg="A folder cannot be shared with another record"):
                    new_record2.record_folder_id = new_folder
                new_folder.write({'res_model': new_record._name, 'res_id': new_record.id})
                with self.assertRaises(
                        UserError, msg="A folder linked to a record cannot be assigned to another record"):
                    new_folder.write({'res_model': new_record._name, 'res_id': new_record2.id})

        # Check that a folder coming from a default value is linked too.
        folder = Document.create({'name': 'defaulted', 'type': 'folder'})
        record = Record.with_context(default_record_folder_id=folder.id).create({'name': 'defaulted record'})
        self.assertEqual(record.record_folder_id, folder)
        self.assertEqual(folder.res_id, record.id, "A defaulted folder is linked too")
        with self.assertRaises(UserError, msg="A defaulted folder is taken like any other"):
            Record.create({'name': 'thief', 'record_folder_id': folder.id})

        # Check that only a folder can be linked.
        target = Document.create({'name': 'shortcut target', 'type': 'folder'})
        binary = Document.create({'name': 'file.txt', 'raw': b'content'})
        record = Record.create({'name': 'record'})
        for candidate in (target.action_create_shortcut(), binary):
            with self.subTest(candidate=candidate.type):
                with self.assertRaises(UserError, msg="A shortcut or a document cannot be a record folder"):
                    record.record_folder_id = candidate
                self.assertFalse(record.record_folder_id, "Nothing is written when refused")
                with self.assertRaises(UserError, msg="A shortcut or a binary cannot be a record folder"):
                    Record.create({'name': 'record', 'record_folder_id': candidate.id})
                self.assertFalse(candidate.res_model, "The refused candidate stays unlinked")

        # Check that copying a record neither shares nor steals the folder of the original.
        folder = Document.create({'name': 'copied', 'type': 'folder'})
        record = Record.create({'name': 'record', 'record_folder_id': folder.id})
        self.assertFalse(record.copy().record_folder_id, "The copy gets no folder")
        self.assertEqual(folder.res_id, record.id, "The original keeps its folder")

        # Check that a folder linked to a record of another model raises an error.
        foreign_folder, dangling_folder = Document.create(
            [{'name': name, 'type': 'folder'} for name in ('foreign', 'dangling')])
        foreign_folder.write({'res_model': self.mixin_record._name, 'res_id': self.mixin_record.id})
        dangling_folder.write({'res_model': self.mixin_record._name, 'res_id': 2 ** 31 - 1})
        for candidate in (foreign_folder, dangling_folder):
            with self.subTest(folder=candidate.name):
                with self.assertRaises(UserError, msg="This folder is already linked to another record."):
                    Record.create({'name': 'record', 'record_folder_id': candidate.id})

        # Check that the folder a record leaves behind keeps its link, but stays fixable.
        folder, current_folder = Document.create(
            [{'name': name, 'type': 'folder'} for name in ('left behind', 'current')])
        record = Record.create({'name': 'record', 'record_folder_id': folder.id})
        record.record_folder_id = current_folder
        folder.write({'res_model': False, 'res_id': False})
        self.assertFalse(folder.res_model, "The stale link can be cleared")
        other_record = Record.create({'name': 'other record', 'record_folder_id': folder.id})
        self.assertEqual(folder.res_id, other_record.id, "The freed folder can be reused")
        with self.assertRaises(UserError, msg="The folder in use is still protected"):
            current_folder.write({'res_model': False, 'res_id': False})

        # Check that clearing the record folder field leaves the folder linked, and fixable.
        record.record_folder_id = False
        self.assertEqual(current_folder.res_id, record.id, "The folder keeps its link")
        current_folder.write({'res_model': False, 'res_id': False})
        self.assertFalse(current_folder.res_model)

        # Check that deleting the folder leaves no dangling reference on the record.
        folder = Document.create({'name': 'to unlink', 'type': 'folder'})
        record = Record.create({'name': 'record', 'record_folder_id': folder.id})
        folder.unlink()
        record.invalidate_recordset()
        self.assertFalse(record.record_folder_id, "No dangling reference on the record")

        # Check that assigning a folder in batch to multiple record raises an error.
        folder = Document.create({'name': 'assign multi', 'type': 'folder'})
        records = Record.create([{'name': f't{idx}'} for idx in range(2)])
        with self.assertRaises(UserError, msg="The folder is already linked."):
            Record.create([{'name': f't{idx}', 'record_folder_id': folder.id} for idx in range(2)])
        with self.assertRaises(UserError, msg="The folder is already linked."):
            records.record_folder_id = folder
        self.assertFalse(folder.res_model)

    def test_unlink_record_resets_folder_link(self):
        """Test that deleting a record remove the links of the linked documents."""
        self.records[0].record_folder_id.active = True
        documents = self.env['documents.document'].create([{
            'name': 'Test url', 'folder_id': folder.id, 'url': 'https://odoo.com', 'type': 'url',
            'res_model': record._name, 'res_id': record.id}
            for folder, record in zip(self.folders, self.records)])
        self.records.unlink()
        for folder, document in zip(self.folders, documents):
            with self.subTest(folder.name):
                self.assertFalse(folder.res_model)
                self.assertFalse(folder.res_id)
                self.assertFalse(document.res_model)
                self.assertFalse(document.res_id)

    @users('documents@example.com')
    def test_create_values_inheritance_from_record(self):
        """Check document mixin values inheritance."""
        records, folders = self.records[:2], self.folders[:2]
        tag = self.env['documents.tag'].sudo().create({'name': 'Record Tag'})
        # Access is granted via access_internal only: the creator has no explicit access member roles.
        folders.sudo().write({'access_internal': 'edit'})
        folders.sudo().action_update_access_rights(partners={self.doc_user.partner_id: (False, False)})
        records[0].write({
            'document_partner_id': self.internal_user.partner_id.id,
            'document_tag_ids': [Command.set(tag.ids)],
        })
        records[1].write(
            {'document_owner_id': self.internal_user.id, 'document_member_ids': self.doc_user.partner_id.ids})

        docs = self.env['documents.document'].create([
            {'name': 'inherited doc', 'type': 'binary', 'raw': b'test', 'folder_id': folder.id} |
            ({'owner_id': owner_id} if owner_id is not None else {})
            for folder, owner_id in ((folders[0], self.doc_user.id), (folders[1], None), (folders[0], None))])

        self.assertEqual(docs.mapped('res_model'), ['documents.mixin.test.folder.per.instance'] * 3)
        self.assertEqual(docs.mapped('res_id'), [records[0].id, records[1].id, records[0].id])

        # Test that mixin values are applied when not forced
        self.assertEqual(
            docs[0].owner_id, self.doc_user,
            'An explicit owner_id passed in create vals is preserved and not overridden by the mixin')
        # Tests that the mixin owner is applied even if the acting user loses write access as a result.
        self.assertEqual(
            docs[1].owner_id, self.internal_user,
            'The mixin _get_document_owner is applied when it returns a valid user')
        self.assertFalse(
            docs[2].owner_id,
            'No owner is set when the mixin _get_document_owner returns empty and no explicit owner is given')
        self.assertEqual(docs[0].sudo().user_permission, 'edit')
        self.assertEqual(docs[1].sudo().user_permission, 'view',
                         'The creator gets the role defined by the record members')
        self.assertEqual(docs[2].sudo().user_permission, 'none', 'The creator does not keep an edit role')
        self.assertEqual(docs[0].partner_id, self.internal_user.partner_id)
        self.assertEqual(docs[0].tag_ids, tag)

        # Check that document mixin values are not applied on folders.
        folders[0].sudo().write({'access_via_link': 'edit', 'access_internal': 'edit'})
        subfolder = self.env['documents.document'].create(
            {'name': 'subfolder', 'type': 'folder', 'folder_id': folders[0].id})
        self.assertEqual(subfolder.res_model, records[0]._name)
        self.assertEqual(
            subfolder.access_via_link, 'edit',
            "access_link inherited from the parent folder (mixin values not applied)")
        self.assertEqual(
            subfolder.access_internal, 'edit',
            "access_internal inherited from the parent folder (mixin values not applied)")
        self.assertEqual(
            subfolder.owner_id, self.doc_user,
            "The creator must remain the owner (mixin values not applied)")
        self.assertFalse(subfolder.partner_id)
        self.assertFalse(subfolder.tag_ids)
        self.assertFalse(
            subfolder.access_ids.filtered(lambda a: a.partner_id == self.internal_user.partner_id),
            'Access members of the mixin not applied')
