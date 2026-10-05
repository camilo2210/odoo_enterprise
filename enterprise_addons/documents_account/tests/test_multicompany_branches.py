from odoo.addons.documents_account.tests.test_documents import TestCaseDocumentsBridgeAccount
from odoo.exceptions import AccessError
from odoo.tests import users
from odoo.tests.common import tagged


@tagged('test_document_bridge')
class TestCaseDocumentsBridgeAccountBranches(TestCaseDocumentsBridgeAccount):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_parent = cls._create_company(name="Company Parent")
        cls.child_company_allowed = cls._create_company(parent_id=cls.company_parent.id, name="Child Company Allowed")
        cls.child_company_disabled = cls._create_company(parent_id=cls.company_parent.id, name="Child Company Disabled")
        child_company_other_data = cls.setup_other_company(parent_id=cls.company_parent.id, name="Child Company Other")
        cls.child_company_other = child_company_other_data['company']

        cls.env.user.company_id = cls.child_company_allowed
        cls.env.user.company_ids = cls.child_company_allowed | cls.company_parent | cls.child_company_disabled
        ctx = {"allowed_company_ids": cls.child_company_allowed.ids}
        cls.env = cls.env["base"].with_context(ctx).with_company(cls.child_company_allowed).env
        cls.internal_user_child_company = cls._create_new_internal_user()

        cls.invoice = cls.init_invoice("out_invoice", amounts=[1000], post=True)
        cls.company_parent_folder = cls.env["documents.account.folder.setting"].sudo().search(
            [("journal_id", "=", cls.invoice.journal_id.id)]).folder_id.sudo(False)

        cls.other_cash_folder = cls.env["documents.account.folder.setting"].sudo().search(
            [("journal_id", "=", child_company_other_data['default_journal_cash'].id)]).folder_id
        cls.other_cash_folder.sudo().action_update_access_rights(partners={
            cls.env.user.partner_id.id: ('edit', False),
            cls.internal_user_child_company.partner_id.id: ('edit', False),
        })
        cls.other_cash_folder = cls.other_cash_folder.with_env(cls.env)

    def test_init_data(self):
        self.assertEqual(self.child_company_allowed.account_folder_id, self.company_parent.account_folder_id)
        self.assertEqual(self.env.user.login, 'accountman')
        self.assertEqual(self.env.company, self.child_company_allowed)
        self.assertEqual(self.company_parent_folder.user_permission, 'edit')
        self.assertEqual(self.company_parent_folder.with_user(self.internal_user_child_company).user_permission,
                         'edit')
        self.assertEqual(self.company_parent_folder.access_internal, 'edit')
        self.assertEqual(self.company_parent_folder.company_id, self.company_parent)
        self.assertFalse(self.company_parent_folder.is_protected,
                         "Sync account folder are not protected for admin")
        self.assertNotIn(self.company_parent_folder,
                         self.env['documents.document'].search([('is_protected', '=', True)]))
        self.assertEqual(self.internal_user_child_company.company_ids, self.child_company_allowed,
                         "Internal user belongs only to the allowed child company")
        self.assertEqual(self.other_cash_folder.user_permission, 'edit')
        self.assertEqual(self.other_cash_folder.with_user(self.internal_user_child_company).user_permission, 'edit')
        self.assertEqual(self.other_cash_folder.company_id, self.child_company_other)

    @classmethod
    def get_default_groups(cls):
        return super().get_default_groups() | cls.env.ref("documents.group_documents_manager")

    def test_create_in_parent_company_folder(self):
        """Test document creation in parent sync and regular folders by a child company."""
        child_folder = self.env["documents.document"].create({
            "name": "Child Company Folder",
            "folder_id": self.company_parent_folder.id,
            "type": "folder"
        })
        self.assertEqual(child_folder.user_permission, "edit")
        self.assertEqual(child_folder.company_id, self.child_company_allowed)

        no_sync_folder = self.env["documents.document"].with_company(self.company_parent).create({
            "name": "No Sync Folder",
            "type": "folder",
            "access_internal": "edit",
            "company_id": self.company_parent.id,
        })
        test_child_vals = {
            "name": "No Sync Folder Child",
            "type": "folder",
            "folder_id": no_sync_folder.id,
        }
        ctx = {"allowed_company_ids": (self.company_parent | self.child_company_allowed).ids}
        DocumentsWithBothCompanies = self.env["documents.document"].with_context(ctx)
        for vals_company_id, expected_company_id in (
            (None, self.company_parent),
            (False, self.env["res.company"]),
            (self.child_company_allowed.id, self.child_company_allowed)
        ):
            with self.subTest(vals_company_id=vals_company_id):
                no_sync_folder_child = DocumentsWithBothCompanies.create(
                    test_child_vals | ({"company_id": vals_company_id} if vals_company_id is not None else {})
                )
                self.assertEqual(no_sync_folder_child.company_id, expected_company_id)

    def test_sync_using_parent_setting(self):
        """Test document synchronization using parent company's account setting by a child company user."""
        wizard = self.env["account.move.send.wizard"].create({
            "move_id": self.invoice.id,
        })
        wizard.action_send_and_print()
        attachments = self.invoice.attachment_ids | self.invoice.invoice_pdf_report_id
        documents = attachments.document_ids
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents.company_id, self.child_company_allowed)

    def test_account_create_account_move(self):
        """Test account move creation from Document (server action) using parent company's synchronization settings."""
        # Apply the action on a document without company
        self.assertFalse(self.document_pdf.company_id)
        self.assertNotEqual(self.document_pdf.folder_id, self.company_parent_folder)
        self.document_pdf.account_create_account_move('out_invoice')
        self.assertEqual(self.document_pdf.company_id, self.child_company_allowed)
        self.assertEqual(self.document_pdf.folder_id, self.company_parent_folder)

        # Apply the action on a document with the parent company
        self.document_txt.company_id = self.company_parent
        self.assertNotEqual(self.document_txt.folder_id, self.company_parent_folder)
        self.document_txt.account_create_account_move('out_invoice')
        self.assertEqual(
            self.document_txt.company_id, self.child_company_allowed,
            "Moving the documents in the company parent triggers the company inheritance "
            "which is altered to match the selected company if possible.")
        self.assertEqual(self.document_txt.folder_id, self.company_parent_folder)

    def test_is_protected_manager(self):
        """Test that account sync folders are not protected for managers."""
        self.assertFalse(self.company_parent_folder.is_protected)
        self.assertTrue(self.other_cash_folder.is_protected)
        self.assertNotIn(self.company_parent_folder,
                         self.env['documents.document'].search([('is_protected', '=', True)]))
        self.assertNotIn(self.other_cash_folder, self.env['documents.document'].search([('is_protected', '=', False)]))
        self.company_parent_folder.name = "Change allowed"
        with self.assertRaises(AccessError):
            self.other_cash_folder.name = "Change not allowed"

    @users('internal_user')
    def test_is_protected_internal_user(self):
        """Test that account sync folders are protected for non-manager."""
        company_parent_folder = self.company_parent_folder.with_env(self.env)
        other_cash_folder = self.other_cash_folder.with_env(self.env)
        self.assertTrue(company_parent_folder.is_protected,
                        "Account-synced folders can only be modified by an administrator.")
        self.assertTrue(other_cash_folder.is_protected)
        self.assertLessEqual(company_parent_folder | other_cash_folder,
                             self.env['documents.document'].search([('is_protected', '=', True)]))
        with self.assertRaises(AccessError):
            company_parent_folder.name = "Not allowed"
        with self.assertRaises(AccessError):
            other_cash_folder.name = "Not allowed"
        self.env['documents.document'].create([
            {'name': 'User can still add documents in those folders', 'raw': b'data', 'folder_id': folder_id}
            for folder_id in (company_parent_folder | other_cash_folder).folder_id.ids])

    def test_is_company_allowed(self):
        """Test that account sync folders are visible even if not in the allowed companies but a parent of them."""
        self.assertTrue(self.company_parent_folder.is_company_allowed)
        self.assertLessEqual(self.company_parent_folder,
                             self.env['documents.document'].search([('is_company_allowed', '=', True)]))
