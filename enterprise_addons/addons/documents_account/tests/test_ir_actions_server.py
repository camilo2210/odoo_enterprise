from itertools import product
from unittest.mock import patch

from odoo import Command
from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments
from odoo.addons.documents_account.tests.common import DocumentsAccountActionsServerCommon
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged


@tagged('test_document_bridge')
class TestIrActionsServer(DocumentsAccountActionsServerCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_documents_account_record_create(self):
        """Test documents_account_record_create action server type (state)."""
        test_cases = [
            ('in_invoice', 'purchase'),
            ('in_refund', 'purchase'),
            ('in_receipt', 'purchase'),
            ('out_invoice', 'sale'),
            ('out_refund', 'sale'),
            ('entry', 'general'),
        ]

        for (move_type, journal_type), with_journal in product(test_cases, (True, False)):
            with self.subTest(move_type=move_type, with_journal=with_journal):
                expected_journal = self.journals_by_type[journal_type]

                action = self.env['ir.actions.server'].create({
                    'name': f'test {move_type}',
                    'model_id': self.env['ir.model']._get_id('documents.document'),
                    'state': 'documents_account_record_create',
                    'documents_account_create_model': f'account.move.{move_type}',
                    'documents_account_journal_id': expected_journal.id if with_journal else False,
                    'usage': 'documents_embedded',
                })

                document = self.document_pdf.copy()
                document.folder_id._embed_action(action.id)
                self._run_action_and_assert_sync(action, document, expected_journal)

    def test_documents_account_standard_actions(self):
        """Test the pre-configured financial server actions work as expected."""
        for journal_type, action_xml_ids in self.actions_by_type.items():
            self.assertTrue(action_xml_ids)
            for action_xml_id in action_xml_ids:

                action = self.env.ref(action_xml_id)
                expected_journal = self.journals_by_type[journal_type]

                journal_folder_name = self.journal_type_labels[expected_journal.type]
                journal_folder = self.env['documents.document'].search([
                    *self.env['account.journal']._check_company_domain(self.env.company),
                    ('name', '=', journal_folder_name),
                ], limit=1)

                folders = self.finance_folder | journal_folder
                embedded_actions = folders._get_folder_embedded_actions(folders.ids)
                self.assertIn(action.id, embedded_actions[self.finance_folder.id].action_id.ids)
                self.assertIn(action.id, embedded_actions[journal_folder.id].action_id.ids)

                if journal_type == 'bank':
                    # These are tested in test_documents_full for dependency reasons
                    continue

                with self.subTest(action_name=action.name):
                    document = self.pdf_in_finance_folder.copy()
                    self._run_action_and_assert_sync(action, document, expected_journal)

    def test_documents_account_record_create_on_invalid_model(self):
        """Test that calling a documents_account_record_create action on a non-document record does nothing."""
        partner = self.env['res.partner'].create({'name': 'test'})
        with patch.object(self.env.registry["documents.document"], 'account_create_account_bank_statement') as mock:
            action = self.env['ir.actions.server'].create({
                'name': 'account.bank.statement',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.bank.statement',
            })
            action.with_context({'active_model': 'res.partner', 'active_id': partner.id}).run()
            mock.assert_not_called()

    def test_documents_account_record_create_documents_only(self):
        """Test model enforcement on documents_account_record_create server action (can only be applied on Document)."""
        with self.assertRaises(ValidationError, msg='"New Journal Entry" can only be applied to Document.'):
            self.env['ir.actions.server'].create({
                'name': 'Wrong model',
                'model_id': self.env['ir.model']._get_id('res.partner'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
            })

    def test_multi_actions_end_destinations(self):
        source_folder = self.folder_a
        destination_folder = self.folder_a_a
        purchase_journal = self.journals_by_type['purchase']

        def get_create_action(seq=5):
            return self.env['ir.actions.server'].create({
                'name': 'Create Vendor Bill',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
                'documents_account_journal_id': purchase_journal.id,
                'usage': 'documents_embedded',
                'sequence': seq,
            })

        def get_move_action(folder, seq=5):
            return self.env['ir.actions.server'].create({
                'name': f'Move to {folder.name}',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'object_write',
                'update_path': 'folder_id',
                'resource_ref': f'documents.document,{folder.id}',
                'sequence': seq,
            })

        def run_scenario(child_ids, expected_folder):
            doc = self.document_pdf.copy()
            doc.folder_id = source_folder
            doc.tag_ids = [Command.clear()]

            parent_action = self.env["ir.actions.server"].create({
                "name": "Multi Wrapper",
                "state": "multi",
                "model_id": self.env["ir.model"]._get_id("documents.document"),
                "child_ids": child_ids,
                "usage": "documents_embedded",
            })

            source_folder._embed_action(parent_action.id)

            parent_action.with_context(active_model="documents.document", active_id=doc.id).run()
            self.assertEqual(doc.folder_id.name, expected_folder)

        with self.subTest("Multi Action [Move -> Create] - Ends up in sync folder"):
            run_scenario(
                [get_move_action(destination_folder).id, get_create_action(seq=10).id],
                expected_folder=self.journal_type_labels[purchase_journal.type],
            )

        with self.subTest("Multi Action [Create -> Move] - Ends up in move folder"):
            run_scenario(
                [get_create_action(seq=1).id, get_move_action(destination_folder).id],
                expected_folder=destination_folder.name,
            )


@tagged('test_document_bridge')
class TestIrActionsServerTag(TransactionCaseDocuments):

    def test_documents_action_tag_operation(self):
        """Test document move and tag add/remove via server action."""
        server_action_1, server_action_2 = self.env['ir.actions.server'].create([
            {
                'name': 'Move and add tags',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
                'documents_account_journal_id': False,
                'documents_folder_id': self.folder_a.id,
                'documents_add_tag_ids': (self.tag_a | self.tag_a_a).ids,
            },
            {
                'name': 'Remove tag_a',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'documents_account_record_create',
                'documents_account_create_model': 'account.move.in_invoice',
                'documents_account_journal_id': False,
                'documents_add_tag_ids': self.tag_a_a.ids,
                'documents_remove_tag_ids': self.tag_a.ids,
            },
        ])

        self.assertEqual(len(server_action_1.child_ids), 3)
        self.assertEqual(len(server_action_2.child_ids), 2)

        documents = self.document_txt | self.document_gif

        for document in documents:
            self.assertEqual(document.folder_id, self.folder_b)
            self.assertNotIn(self.tag_a, document.tag_ids)
            self.assertNotIn(self.tag_a_a, document.tag_ids)

        server_action_1.with_context(active_model='documents.document', active_ids=documents.ids).run()

        for document in documents:
            self.assertEqual(document.folder_id, self.folder_a, 'Document moved to folder A')
            self.assertIn(self.tag_a, document.tag_ids, 'tag_a should have been added')
            self.assertIn(self.tag_a_a, document.tag_ids, 'tag_a_a should have been added')

        server_action_2.with_context(active_model='documents.document', active_ids=documents.ids).run()

        for document in documents:
            self.assertNotIn(self.tag_a, document.tag_ids, 'tag_a should have been removed')
            self.assertIn(self.tag_a_a, document.tag_ids, 'tag_a_a should still be present')

    def test_inverse_documents_folder_id(self):
        """Test that changing the folder updates the existing child action."""
        action = self.env['ir.actions.server'].create({
            'name': 'Test Folder Update',
            'model_id': self.env['ir.model']._get_id('documents.document'),
            'state': 'documents_account_record_create',
            'documents_account_create_model': 'account.move.in_invoice',
            'documents_folder_id': self.folder_a.id,
        })

        self.assertEqual(len(action.child_ids), 1)
        child_action = action.child_ids
        self.assertEqual(child_action.state, 'object_write')
        self.assertEqual(child_action.value, str(self.folder_a.id))

        action.documents_folder_id = self.folder_b
        self.assertEqual(len(action.child_ids), 1, 'Folder change should update, not create a new child action')
        self.assertEqual(action.child_ids, child_action, 'Child action record should be reused')
        self.assertEqual(child_action.value, str(self.folder_b.id), 'Child action value should be updated')

        action.documents_folder_id = False
        self.assertFalse(action.child_ids, 'Child action should be removed')

        action.documents_folder_id = self.folder_a
        self.assertEqual(len(action.child_ids), 1)

        action.state = 'object_write'
        action._compute_documents_folder_id()
        self.assertFalse(action.child_ids, 'Child actions should be removed when state changes')

    def test_constraints_child_actions(self):
        """Test constraints on child actions."""
        parent_action = self.env['ir.actions.server'].create({
            'name': 'Parent Action',
            'model_id': self.env['ir.model']._get_id('documents.document'),
            'state': 'documents_account_record_create',
            'documents_account_create_model': 'account.move.in_invoice',
        })

        with self.assertRaises(ValidationError, msg='Only tag/folder updates are allowed as child actions.'):
            self.env['ir.actions.server'].create({
                'name': 'Invalid Child Path',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'object_write',
                'parent_id': parent_action.id,
                'update_path': 'name',
                'value': 'New Name',
            })

        parent_action.documents_folder_id = self.folder_b.id

        with self.assertRaises(ValidationError, msg='Only one folder move is allowed per action.'):
            self.env['ir.actions.server'].create({
                'name': 'Second Folder Move',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'object_write',
                'parent_id': parent_action.id,
                'update_path': 'folder_id',
                'value': str(self.folder_a.id),
            })

        add_tag = self.env['ir.actions.server'].create({
            'name': 'Add Tag',
            'model_id': self.env['ir.model']._get_id('documents.document'),
            'state': 'object_write',
            'parent_id': parent_action.id,
            'update_path': 'tag_ids',
            'update_m2m_operation': 'add',
            'resource_ref': f'documents.tag,{self.tag_a.id}',
        })

        with self.assertRaises(ValidationError, msg='Cannot add and remove tags at the same time.'):
            self.env['ir.actions.server'].create({
                'name': 'Remove Tag',
                'model_id': self.env['ir.model']._get_id('documents.document'),
                'state': 'object_write',
                'parent_id': parent_action.id,
                'update_path': 'tag_ids',
                'update_m2m_operation': 'remove',
                'resource_ref': f'documents.tag,{self.tag_a.id}',
            })

        add_tag_2 = add_tag.copy()
        with self.assertRaises(ValidationError, msg='Cannot add and remove tags at the same time.'):
            add_tag_2.update_m2m_operation = 'remove'
