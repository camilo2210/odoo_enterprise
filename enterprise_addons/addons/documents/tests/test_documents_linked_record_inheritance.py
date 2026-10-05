# Part of Odoo. See LICENSE file for full copyright and licensing details.
from functools import reduce

from .test_documents_common import TransactionCaseDocuments
from odoo import Command
from odoo.tests import HttpCase, users
from odoo.tests.common import RecordCapturer, new_test_user


class TestDocumentsLinkedRecordsInheritance(HttpCase, TransactionCaseDocuments):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner, cls.other_partner = cls.env['res.partner'].create([
            {'name': "Linked Partner"},
            {'name': "Other Linked Partner"},
        ])
        Document = cls.env['documents.document']
        # Avoid dealing in the test with root folders that are not writable by standard document user
        root_folder, aaa_doc_not_linked, aad_doc_linked_other, out_tree_linked_other = Document.create([
            {'type': 'folder', 'name': 'root', 'owner_id': cls.doc_user.id},
            {'name': 'AAA: doc not linked', 'type': 'binary', 'raw': b'test'},
            {'name': 'AAD: doc linked other', 'type': 'binary', 'raw': b'test',
             'res_model': cls.other_partner._name, 'res_id': cls.other_partner.id},
            {'name': 'Out-tree linked other', 'type': 'binary', 'raw': b'test',
             'res_model': cls.other_partner._name, 'res_id': cls.other_partner.id,
             'owner_id': cls.doc_user.id}])
        folder, shortcut_out_tree_target_in_tree_not_linked, shortcut_out_tree_target_in_tree_linked = Document.create(
            [
                {'name': 'A', 'type': 'folder', 'folder_id': root_folder.id,
                 'children_ids': [
                     Command.create({'name': 'AA', 'type': 'folder',
                                     'children_ids': [
                                         Command.link(aaa_doc_not_linked.id),
                                         Command.create({'name': 'AAB: shortcut in-tree target out-tree not linked',
                                                         'owner_id': cls.doc_user.id,
                                                         'shortcut_document_id': cls.document_gif.id}),
                                         Command.create({'name': 'AAC: shortcut in-tree target in-tree not linked',
                                                         'owner_id': cls.doc_user.id,
                                                         'shortcut_document_id': aaa_doc_not_linked.id}),
                                         Command.link(aad_doc_linked_other.id),
                                         Command.create({'name': 'AAE: shortcut in-tree target in-tree linked other',
                                                         'owner_id': cls.doc_user.id,
                                                         'shortcut_document_id': aad_doc_linked_other.id}),
                                         Command.create({'name': 'AAF: shortcut in-tree target out-tree linked other',
                                                         'owner_id': cls.doc_user.id,
                                                         'shortcut_document_id': out_tree_linked_other.id}),
                                         Command.create({'name': 'AAG: doc linked', 'type': 'binary', 'raw': b'test',
                                                         'res_model': cls.partner._name, 'res_id': cls.partner.id,
                                                         'owner_id': cls.doc_user.id}),
                                     ]}),
                     Command.create({'name': 'AB: linked to other (barrier)', 'type': 'folder',
                                     'res_model': 'res.partner', 'res_id': cls.other_partner.id,
                                     'children_ids': [
                                         Command.create(
                                             {'name': 'ABA: doc not linked', 'type': 'binary', 'raw': b'test',
                                              'res_model': False, 'res_id': False}),
                                         Command.create(
                                             {'name': 'ABB: folder not linked', 'type': 'folder',
                                              'res_model': False, 'res_id': False}),
                                     ]}),
                     Command.create({'name': 'AC: readonly (barrier)', 'type': 'folder',
                                     'children_ids': [
                                         Command.create(
                                             {'name': 'ACA: doc not linked', 'type': 'binary', 'raw': b'test',
                                              'owner_id': cls.doc_user.id}),
                                     ]}),
                 ],
                 },
                {
                    'name': 'shortcut out-tree target in-tree not linked',
                    'shortcut_document_id': aaa_doc_not_linked.id, 'owner_id': cls.doc_user.id
                },
                {
                    'name': 'shortcut out-tree target in-tree linked', 'shortcut_document_id': aad_doc_linked_other.id,
                    'owner_id': cls.doc_user.id
                },
            ])
        cls.documents = (cls.env['documents.document'].search([('id', 'child_of', folder.id)])
                         | shortcut_out_tree_target_in_tree_not_linked | shortcut_out_tree_target_in_tree_linked)
        cls.doc_by_name = cls.documents.grouped('name')

        cls.doc_by_name['A'].action_update_access_rights(partners={cls.doc_user.partner_id: ('edit', False)})
        cls.doc_by_name['AC: readonly (barrier)'].action_update_access_rights(
            partners={cls.doc_user.partner_id: ('view', False)})

    def test_initial_values(self):
        """Verify initial res_model/res_id values and per-user access rights on the test tree."""
        linked_other = reduce(lambda a, b: a | b,
                        (self.doc_by_name[name]
                         for name in ('AB: linked to other (barrier)', 'AAD: doc linked other',
                                      'AAE: shortcut in-tree target in-tree linked other',
                                      'AAF: shortcut in-tree target out-tree linked other',
                                      'shortcut out-tree target in-tree linked')))
        linked = self.doc_by_name['AAG: doc linked']
        not_linked = self.documents - linked_other - linked
        self.assertLinkedTo(linked_other.mapped('name'), self.other_partner._name, self.other_partner.id)
        self.assertLinkedTo(linked.mapped('name'), self.partner._name, self.partner.id)
        self.assertLinkedTo(not_linked.mapped('name'), False, False)
        readonly = self.doc_by_name['AC: readonly (barrier)']
        writable = self.documents - readonly
        self.assertEqual(readonly.with_user(self.doc_user).mapped('user_permission'), ['view'])
        self.assertEqual(writable.with_user(self.doc_user).mapped('user_permission'), ['edit'] * 15)

    @users('documents@example.com')
    def test_propagation_write(self):
        """Test propagation of res_model, res_id."""
        # Linking a folder propagates to unlinked descendants
        self.doc_by_name['A'].with_env(self.env).write({'res_model': self.partner._name, 'res_id': self.partner.id})
        self.assertLinkedTo(('A', 'AA'),
                            self.partner._name, self.partner.id,
                            'Linking a folder should propagate to not linked sub-folders only (not other documents)')
        self.assertLinkedTo(('AAA: doc not linked', 'AAC: shortcut in-tree target in-tree not linked'),
                            False, False,
                            'Only folders are affected. Regular document or shorcut not.')
        self.assertLinkedTo(('AB: linked to other (barrier)',), self.other_partner._name, self.other_partner.id,
                            'Already Linked folder is not modified')
        self.assertLinkedTo(('AC: readonly (barrier)', 'ACA: doc not linked'), False, False,
                            'Readonly folder acts as a barrier: descendant are not modified even if writable')
        # Shortcuts
        self.assertLinkedTo((
            'AAC: shortcut in-tree target in-tree not linked',
            'shortcut out-tree target in-tree not linked',
        ), False, False,
            'Shortcut whose in-tree target was not linked are not affected')
        self.assertLinkedTo(
            ('AAB: shortcut in-tree target out-tree not linked',), False, False,
            'Shortcut whose target is outside the tree remains unlinked (no propagation through shortcut)')
        self.assertLinkedTo((
            'AAE: shortcut in-tree target in-tree linked other',
            'shortcut out-tree target in-tree linked',
            'AAF: shortcut in-tree target out-tree linked other',
        ), self.other_partner._name, self.other_partner.id,
            'Shortcuts whose targets are already linked keep their existing link')

        # Unlinking a linked folder does NOT propagate to children.
        self.doc_by_name['A'].with_env(self.env).write({'res_model': False, 'res_id': False})
        self.assertLinkedTo(('A',), False, False, 'Folder is unlinked')
        self.assertLinkedTo(('AA',), self.partner._name, self.partner.id, 'Child must KEEP its propagated link')

        # Relinking a linked folder re-links it and propagates to unlinked child folders."""
        self.doc_by_name['AB: linked to other (barrier)'].with_env(self.env).write(
            {'res_model': self.partner._name, 'res_id': self.partner.id})
        self.assertLinkedTo(('AB: linked to other (barrier)', 'ABB: folder not linked'),
                            self.partner._name, self.partner.id,
                            'Re-linking a linked folder propagates the new link to its unlinked child folders')
        self.assertLinkedTo(('ABA: doc not linked',), False, False, 'Only folder are affected.')

    @users('documents@example.com')
    def test_copy_res_fields_not_copied(self):
        """Copying a linked folder does NOT copy res_model/res_id; inherits from destination parent."""
        shortcut_partner = self.env['documents.document'].create(
            {'shortcut_document_id': self.doc_by_name['AAG: doc linked'].id, 'folder_id': self.doc_by_name['A'].id})
        documents = (reduce(
            lambda a, b: a | b,
            (self.doc_by_name[name]
             for name in ('AAG: doc linked', 'AAA: doc not linked',
                          'AAE: shortcut in-tree target in-tree linked other'))) | shortcut_partner).with_env(self.env)

        # Copy in another folder
        copied_documents = documents.with_env(self.env).copy({
            'folder_id': self.doc_by_name['AB: linked to other (barrier)'].id})
        self.assertEqual(copied_documents[:3].mapped('res_id'), [self.other_partner.id] * 3,
                         'The copied documents inherit from the new parent folder, even if they were already linked.')
        self.assertEqual(copied_documents[3].res_id, self.partner.id,
                         'The copied shortcut does not inherit the res_model and res_id from its new parent folder.')
        self.assertEqual(copied_documents.mapped('res_model'), ['res.partner'] * 4)

        # Copy in another folder with forced res_model, res_id
        copied_documents = self.doc_by_name['AAG: doc linked'].with_env(self.env).copy({
            'folder_id': self.doc_by_name['AB: linked to other (barrier)'].id,
            'res_model': 'res.partner', 'res_id': self.partner.id})
        self.assertEqual(copied_documents.res_id, self.partner.id,
                         'The res_model and res_id defaults must be honored.')

        # Copy in the same folder, no defaults
        copied_documents = documents.copy()
        self.assertFalse(copied_documents[0].res_id,
                         'Copied linked document in an unlinked folder should not be linked')
        self.assertFalse(copied_documents[1].res_id,
                         'Copied unlinked document in an unlinked folder should not be linked')
        self.assertEqual(copied_documents[2].res_id, self.other_partner.id, 'Copied shortcut should retain its link')
        self.assertEqual(copied_documents[3].res_id, self.partner.id, 'Copied shortcut should retain its link')

    @users('documents@example.com')
    def test_propagation_move(self):
        """Test propagation on move."""
        # Moving a shortcut under a linked folder does NOT trigger inheritance of res_model/res_id
        shortcut = self.doc_by_name['AAC: shortcut in-tree target in-tree not linked'].with_env(self.env)
        self.assertEqual(shortcut.res_model, False)
        self.assertEqual(shortcut.res_id, False)
        shortcut.folder_id = self.doc_by_name['AB: linked to other (barrier)']
        self.assertLinkedTo(
            ('AAC: shortcut in-tree target in-tree not linked',), False, False,
            'Shortcut moved under a linked folder must not inherit res_model/res_id')
        shortcut.folder_id = self.doc_by_name['AA']  # Move it back

        folder_b = self.env['documents.document'].sudo().create(
            {'name': 'B', 'type': 'folder', 'owner_id': self.doc_user.id,
             'res_model': 'res.partner', 'res_id': self.other_partner.id})
        # Move an unlinked folder under a linked folder: unlinked docs inherit the link, linked docs are untouched
        self.doc_by_name['A'].with_env(self.env).folder_id = folder_b
        self.assertLinkedTo(('A', 'AA', 'AAA: doc not linked'), 'res.partner', self.other_partner.id,
                            'An accessible but not-linked document inherits its linked record from the new parent')
        self.assertLinkedTo(('AC: readonly (barrier)', 'ACA: doc not linked'), False, False,
                            "Inheritance does not cross the barrier")
        self.assertLinkedTo(('AAD: doc linked other',),
                            self.other_partner._name, self.other_partner.id,
                            'Docs already linked to the same record must keep their link')
        self.assertLinkedTo(('AAG: doc linked',), self.partner._name, self.partner.id,
                            'Docs already linked to a different record must not be overwritten')
        # Shortcuts
        self.assertLinkedTo(('AAB: shortcut in-tree target out-tree not linked',), False, False,
                            'Shortcut targeting unlinked document outside the moved subtree must remain unlinked')
        self.assertLinkedTo(('AAC: shortcut in-tree target in-tree not linked',),
                            self.other_partner._name, self.other_partner.id,
                            'Shortcut whose in-tree target was just linked must inherit the link')
        self.assertLinkedTo(
            ('AAE: shortcut in-tree target in-tree linked other', 'AAF: shortcut in-tree target out-tree linked other'),
            self.other_partner._name, self.other_partner.id,
            'Shortcut whose target was not modified must keep its existing link')

        # Move a linked folder under another folder: the folder keeps its link and no propagation occurs.
        folder_linked = self.env['documents.document'].create(
            {'folder_id': self.doc_by_name['A'].id, 'type': 'folder',
             'res_model': self.partner._name, 'res_id': self.partner.id})
        self.doc_by_name['AB: linked to other (barrier)'].with_env(self.env).folder_id = folder_linked
        self.assertLinkedTo(('AB: linked to other (barrier)',), self.other_partner._name, self.other_partner.id,
                            'Moving a linked folder does not alter its link')
        self.assertLinkedTo(('ABA: doc not linked',), False, False,
                            'No propagation through a linked folder (barrier of link)')

        # Moving a linked folder under a not linked parent: the folder keeps its link and no propagation occurs.
        folder_not_linked = self.env['documents.document'].create({'name': 'folder not linked', 'type': 'folder'})
        linked_child = self.doc_by_name['ABA: doc not linked'].with_env(self.env)
        linked_child.write({'res_model': 'res.partner', 'res_id': self.other_partner.id})
        self.doc_by_name['AB: linked to other (barrier)'].with_env(self.env).folder_id = folder_not_linked
        self.assertLinkedTo(('AB: linked to other (barrier)',), 'res.partner', self.other_partner.id,
                            'Linked node keeps its link when moved under unlinked parent')
        self.assertLinkedTo(('ABA: doc not linked',), 'res.partner', self.other_partner.id,
                            'Child of moved node keeps its link (no propagation)')

        # Moving a linked folder under a parent linked to the same record does NOT propagate to unlinked children.
        self.doc_by_name['ABA: doc not linked'].write({'res_model': False, 'res_id': False})
        folder_same_record = self.env['documents.document'].create({
            'name': 'Parent linked to same record', 'type': 'folder', 'folder_id': self.doc_by_name['A'].id,
            'res_model': 'res.partner', 'res_id': self.other_partner.id})
        self.doc_by_name['AB: linked to other (barrier)'].with_env(self.env).folder_id = folder_same_record.id
        self.assertLinkedTo(('AB: linked to other (barrier)',), 'res.partner', self.other_partner.id,
                            'Linked folder keeps its link when moved under a same-record parent')
        self.assertLinkedTo(('ABA: doc not linked',), False, False,
                            'No propagation as the parent record was not modified by the move')

        # Move while resetting the res_model, res_id
        parent, child = self.doc_by_name['A'], self.doc_by_name['AB: linked to other (barrier)']
        parent.write({'res_model': self.partner._name, 'res_id': self.partner.id})
        child.write({'res_model': False, 'res_id': False, 'folder_id': parent.id})
        self.assertFalse(child.res_id,
                         "Resetting the res_model, res_id while moving prevent the inheritance")

        # Neutral operations
        child.folder_id = child.folder_id
        self.assertFalse(child.res_id,
                         "Updating the record folder to the same value doesn't trigger a propagation")
        child.name = 'updating other field'
        self.assertFalse(child.res_id,
                         "Updating another field doesn't trigger a propagation")

    @users('documents@example.com')
    def test_create_inheritance(self):
        """Test inheritance at creation."""
        # Creating a new doc in a linked folder inherits the parent's res_model/res_id
        new_docs = self.env['documents.document'].create([
            {'name': f'New {idx}', 'type': 'binary', 'raw': b'test',
             'folder_id': self.doc_by_name['AB: linked to other (barrier)'].id}
            for idx in range(2)])
        self.assertEqual(new_docs.mapped('res_model'), ['res.partner'] * 2)
        self.assertEqual(new_docs.mapped('res_id'), [self.other_partner.id] * 2)

        # Creating a new doc in a linked folder with res_model/res_id prevent inheritance
        new_docs = self.env['documents.document'].create([
            {'name': f'New {idx}', 'type': 'binary', 'raw': b'test',
             'res_model': 'res.partner', 'res_id': self.partner.id,
             'folder_id': self.doc_by_name['AB: linked to other (barrier)'].id}
            for idx in range(2)])
        self.assertEqual(new_docs.mapped('res_model'), ['res.partner'] * 2)
        self.assertEqual(new_docs.mapped('res_id'), [self.partner.id] * 2)
        # Same but res_model, res_id brought through the attachment
        attachments = self.env['ir.attachment'].sudo().create([
            {'name': f'New {idx}', 'mimetype': 'text/plain', 'raw': b'test',
             'res_model': 'res.partner', 'res_id': self.partner.id}
            for idx in range(2)])
        new_docs = self.env['documents.document'].create([
            {'attachment_id': attachment.id, 'folder_id': self.doc_by_name['AB: linked to other (barrier)'].id}
            for attachment in attachments])
        self.assertEqual(new_docs.mapped('res_model'), ['res.partner'] * 2)
        self.assertEqual(new_docs.mapped('res_id'), [self.partner.id] * 2)

        # Test that uploaded documents inherit res_model/res_id from the parent folder.
        self.authenticate(self.env.user.login, self.env.user.login)
        with RecordCapturer(self.env['documents.document'], []) as capture:
            res = self.url_open(f'/documents/upload/{self.doc_by_name['AB: linked to other (barrier)'].access_token}',
                                data={'csrf_token': self.csrf_token()},
                                files=[
                                    ('ufile', ('hello1.txt', b"Hello 1", 'text/plain')),
                                    ('ufile', ('hello2.txt', b"Hello 2", 'text/plain')),
                                ],
                                allow_redirects=False,
                                )
            res.raise_for_status()
        documents = capture.records
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents.mapped('res_model'), ['res.partner'] * 2)
        self.assertEqual(documents.mapped('res_id'), [self.other_partner.id] * 2)

    def test_search_panel_hides_linked_record_to_share_user(self):
        """Test that the record linked to a folder is not disclosed to portal users."""
        portal_user = new_test_user(self.env, 'portal_linked_record', groups='base.group_portal')
        folder = self.doc_by_name['AB: linked to other (barrier)']
        folder.action_update_access_rights(partners={portal_user.partner_id: ('view', False)})
        values = self.env['documents.document'].with_user(portal_user).search_panel_select_range('user_folder_id')
        shared = [v for v in values['values'] if v.get('display_name') == folder.name]
        self.assertTrue(shared, 'The shared folder must be visible')
        self.assertFalse(set(shared[0]) & {'res_model_folder', 'res_id_folder', 'res_name_folder'})

    @users('documents@example.com')
    def test_request_inherits_from_nested_folders(self):
        """Test document requests inherit res_model/res_id from parent folder and honor explicit overrides."""
        folder = self.doc_by_name['AB: linked to other (barrier)']
        folder.sudo().action_update_access_rights(partners={self.internal_user.partner_id: ('edit', False)})
        activity_upload_internal = self.env['mail.activity.type'].sudo().create({
            'name': 'request_document', 'category': 'upload_file', 'folder_id': folder.id})
        request_base_vals = {
            'name': 'Wizard Request',
            'requestee_id': self.internal_user.partner_id.id,
            'activity_type_id': activity_upload_internal.id,
            'folder_id': folder.id,
            'activity_date_deadline_range_type': 'days',
            'activity_date_deadline_range': 3,
        }
        document = self.env['documents.request_wizard'].create(request_base_vals).request_document()
        self.assertEqual(document.res_model, 'res.partner')
        self.assertEqual(document.res_id, self.other_partner.id)

        # Upload the requested document
        self.authenticate(self.internal_user.login, self.internal_user.login)
        with RecordCapturer(self.env['ir.attachment'], []) as capture:
            res = self.url_open(f'/documents/upload/{document.access_token}',
                                data={'csrf_token': self.csrf_token()},
                                files=[('ufile', ('requested_file.txt', b"Test", 'text/plain'))],
                                allow_redirects=False)
            res.raise_for_status()
        attachment = capture.records
        self.assertEqual(attachment.res_model, 'res.partner')
        self.assertEqual(attachment.res_id, self.other_partner.id)
        self.assertEqual(document.res_model, 'res.partner')
        self.assertEqual(document.res_id, self.other_partner.id)

        # If the res_model, res_id is forced, it is honored
        document = self.env['documents.request_wizard'].create({
            **request_base_vals,
            'res_model': self.doc_user.partner_id._name,
            'res_id': self.doc_user.partner_id.id,
        }).request_document()
        self.assertEqual(document.res_model, 'res.partner')
        self.assertEqual(document.res_id, self.doc_user.partner_id.id)

    def assertLinkedTo(self, doc_names, res_model, res_id, msg=None):
        self.assertTrue(doc_names)
        for doc in [self.doc_by_name[name] for name in doc_names]:
            with self.subTest(doc_name=doc.name, msg=msg):
                self.assertEqual(doc.res_model, res_model)
                self.assertEqual(doc.res_id, res_id)
                if doc.shortcut_document_id:
                    doc = doc.shortcut_document_id
                    self.assertEqual(doc.res_model, res_model)
                    self.assertEqual(doc.res_id, res_id)
                if doc.attachment_id:
                    self.assertEqual(doc.attachment_id.res_model, res_model if res_model else 'documents.document')
                    self.assertEqual(doc.attachment_id.res_id, res_id if res_id else doc.id)
