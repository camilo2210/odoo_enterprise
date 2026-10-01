from odoo import Command
from odoo.tools import mute_logger
from odoo.addons.documents.tests.test_documents_sharing import TestDocumentsSharingCommon
from odoo.tests import tagged, Form, users


class TestSpreadsheetDocumentsSharing(TestDocumentsSharingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["documents.document"].create({
            "name": "Test folder",
            "type": "folder",
            "access_internal": "view",
            "access_via_link": "view",
        })
        cls.frozen_spreadsheets = cls.env['documents.document'].create([
            {'name': f'Frozen spreadsheet_{i}', 'handler': 'frozen_spreadsheet',
             'folder_id': cls.folder.id, 'owner_id': cls.document_manager.id}
            for i in range(2)
        ])
        cls.spreadsheet = cls.env['documents.document'].create([
            {'name': f'Spreadsheet_{i}', 'handler': 'spreadsheet',
             'folder_id': cls.folder.id, 'owner_id': cls.document_manager.id}
            for i in range(2)
        ])
        cls.non_spreadsheet = cls.env['documents.document'].create([{
            'name': f'Non_spreadsheet_{i}',
            'folder_id': cls.folder.id,
            'owner_id': cls.document_manager.id,
            'raw': 'test',
        } for i in range(2)])
        cls.docs = cls.frozen_spreadsheets | cls.spreadsheet | cls.non_spreadsheet
        (cls.frozen_spreadsheets | cls.spreadsheet | cls.non_spreadsheet).action_update_access_rights(
            partners={cls.doc_user.partner_id: ('view', False), cls.portal_user.partner_id: ('view', False)})
        cls.partners = cls.frozen_spreadsheets[0].access_ids.partner_id

    @staticmethod
    def get_display_names(records):
        return ', '.join(records.sorted('display_name').mapped('display_name'))

    @users("dtdm")
    def test_invite_frozen_edit_error(self):
        with Form(self.create_documents_sharing(self.docs)) as form:
            self.assertFalse(form.error_message_spreadsheet)
            form.invite_partner_ids = self.doc_user.partner_id
            form.invite_role = 'edit'
            self.assertIn("Read only spreadsheet(s):", form.error_message_spreadsheet)
            self.assertIn(self.get_display_names(self.frozen_spreadsheets), form.error_message_spreadsheet)

    @users("dtdm")
    def test_share_frozen_edit_error(self):
        for operation, expected_partners in (
            ('set_doc_user_edit', self.doc_user.partner_id),
            ('set_access_internal_edit', self.env['res.partner']),
            ('set_access_via_link_edit', self.env['res.partner']),
        ):
            with self.subTest(operation=operation), Form(self.create_documents_sharing(self.docs)) as form:
                self.assertFalse(form.error_message_spreadsheet)
                if operation == 'set_doc_user_edit':
                    with self.form_get_access_edit(form, self.doc_user.partner_id) as access_edit_form:
                        access_edit_form.role = 'edit'
                elif operation == 'set_access_internal_edit':
                    form.access_internal = 'edit'
                elif operation == 'set_access_via_link_edit':
                    form.access_via_link = 'edit'
                self.assertIn('Read only spreadsheet(s):', form.error_message_spreadsheet)
                self.assertIn(self.get_display_names(self.frozen_spreadsheets), form.error_message_spreadsheet)
                self.assertIn(self.get_display_names(expected_partners), form.error_message_spreadsheet)

    @users("dtdm")
    def test_removing_illegal_access_after_user_deactivation(self):
        action = self.env["documents.sharing"].action_open(self.spreadsheet.ids)
        doc_sharing = self.assert_open_wizard(action, self.spreadsheet)
        with Form(doc_sharing) as form:
            form.invite_partner_ids = (self.doc_user).partner_id
            form.invite_role = "edit"
        doc_sharing.action_invite_members()
        self.doc_user.action_archive()
        with Form(self.create_documents_sharing(self.spreadsheet)) as form:
            self.assertFalse(form.error_message_spreadsheet)
            self.assertFalse(form.has_warning_partners_without_access)
            with self.form_get_access_edit(
                form, self.doc_user.partner_id
            ) as access_edit_form:
                access_edit_form.is_deleted = True

            self.assertFalse(form.error_message_spreadsheet)
            self.assertFalse(form.has_warning_partners_without_access)

    @users("dtdm")
    def test_freeze_preserves_group_access_and_downgrades_to_view(self):
        group = self.env["res.group.functional"].create({
            "name": "Internal Group",
            "user_ids": [Command.link(self.doc_user.id)],
        })
        spreadsheet = self.spreadsheet[0]
        spreadsheet.action_update_access_rights(
            groups={group: ('edit', False)}
        )

        with mute_logger('odoo.addons.documents.models.documents_document'):
            frozen_action = spreadsheet.action_freeze_and_copy(b"{}", [])
        frozen_spreadsheet = spreadsheet.browse(frozen_action['id'])

        access = frozen_spreadsheet.access_ids.filtered(lambda a: a.group_id == group)
        self.assertTrue(access, "Access should be copied to frozen document")
        self.assertFalse(access.partner_id, "Access should remain group-based (no partner_id)")
        self.assertEqual(
            access.role, "view",
            "Edit access should be downgraded to view on frozen spreadsheet"
        )
