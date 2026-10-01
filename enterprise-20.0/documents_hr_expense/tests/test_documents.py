# -*- coding: utf-8 -*-

import base64
from odoo import Command
from odoo.addons.base.tests.files import PDF_RAW
from odoo.addons.hr_expense.tests.common import TestExpenseCommon
from odoo.addons.documents_account.tests.common import DocumentsAccountTestCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import RecordCapturer

TEXT = base64.b64encode(bytes("workflow bridge project", 'utf-8'))


@tagged('-at_install', 'post_install')
class TestCaseDocumentsBridgeExpense(TestExpenseCommon, DocumentsAccountTestCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.folder_internal = cls.env.ref('documents.document_internal_folder')
        cls.folder_internal.action_update_access_rights(access_internal='edit')

        cls.documents_user = cls.env['res.users'].create({
            'name': "aaadocuments test basic user",
            'login': "aadtbu",
            'email': "aadtbu@yourcompany.com",
            'group_ids': [Command.set([cls.env.ref('documents.group_documents_user').id])],
        })

    def _create_txt_attachment_for_documents_user(self, company=False):
        return self.env['documents.document'].with_user(self.documents_user).with_company(company or self.env.company).create({
            'raw': PDF_RAW,
            'name': 'file.pdf',
            'mimetype': 'application/pdf',
            'folder_id': self.folder_internal.id,
        })

    def test_create_document_to_expense(self):
        """
        Makes sure the hr expense is created from the document.

        Steps:
            - Create user with employee
            - Create attachment
            - Performed action 'Create a Expense'
            - Check if the expense is created
            - Check the res_model of the document

        """
        self.documents_user.sudo().action_create_employee()  # Employee is mandatory in expense
        document_txt = self._create_txt_attachment_for_documents_user()

        self.assertFalse(document_txt.res_model, "The default res model of a document is False.")
        self.assertEqual(document_txt.attachment_id.res_model, 'documents.document', "The default res model of an attachment is documents.document.")
        document_txt.with_user(self.documents_user).document_hr_expense_create_hr_expense()
        self.assertEqual(document_txt.res_model, 'hr.expense', "The document model is updated.")
        self.assertEqual(document_txt.attachment_id.res_model, 'hr.expense', "The attachment model is updated.")
        expense = self.env['hr.expense'].search([('id', '=', document_txt.res_id)])
        self.assertTrue(expense.exists(), 'expense sholud be created.')
        self.assertEqual(document_txt.res_id, expense.id, "Expense should be linked to document")
        self.assertEqual(expense.employee_id, self.documents_user.employee_id)

    def test_sync_expense_receipts_to_documents(self):
        folder_test = self.env['documents.document'].create({'name': 'folder_test', 'type': 'folder'})
        journal_test = self.env['account.journal'].create({
            'name': 'Expenses Test',
            'type': 'purchase',
            'code': 'EXP2',
        })
        self.setup_sync_journal_folder(journal_test, folder_test)

        expense = self.create_expenses({'name': 'Company expense'})
        expense_2 = self.create_expenses({'name': 'Company expense 2'})

        attachment = self.env['ir.attachment'].create({
            'raw': TEXT,
            'name': 'text_1.txt',
            'res_model': 'hr.expense',
            'res_id': expense.id,
        })
        attachment_2 = self.env['ir.attachment'].create({
            'raw': base64.b64encode(bytes("Attachment 2", 'utf-8')),
            'name': 'text_2.txt',
            'res_model': 'hr.expense',
            'res_id': expense_2.id,
        })

        expense.message_main_attachment_id = attachment
        expense_2.message_main_attachment_id = attachment_2
        expenses = expense | expense_2

        expenses.action_submit()
        expenses._do_approve()

        self.post_expenses(expenses)

        bill = expenses.account_move_id
        documents = self.env['documents.document'].search([('attachment_id', 'in', bill.attachment_ids.ids)])

        self.assertItemsEqual(bill.attachment_ids.ids, documents.attachment_id.ids)

        self.assertEqual(bill.message_main_attachment_id.id, bill.attachment_ids.ids[0])
        with RecordCapturer(self.env['documents.document']) as doc_capturer:
            self.env['ir.attachment'].browse(bill.attachment_ids.ids[1]).register_as_main_attachment()
            self.env['documents.document'].flush_model()
        self.assertFalse(doc_capturer.records, "No document created")
        self.assertEqual(bill.message_main_attachment_id.id, bill.attachment_ids.ids[1])

    def test_create_document_to_expense_without_employee(self):
        """
        Make sure UserError is raised when creating expense from document
        while the current user is not linked to an employee and has no rights to create an expense.
        If the current user is not linked to an employee and has rights to create an expense,
        it should create an expense with an empty employee
        Finally if there is no employee in the company, it should create an expense with an empty employee
        """
        # First, user has no employee and no rights
        attachment_txt = self._create_txt_attachment_for_documents_user()
        with self.assertRaisesRegex(UserError, "The current user has no related employee. Please, create one."):
            attachment_txt.with_user(self.documents_user).document_hr_expense_create_hr_expense()

        expense = self.env['hr.expense'].search([('id', '=', attachment_txt.res_id)])
        self.assertFalse(expense.exists())

        # Then, add rights to the user and try to create an expense -> should create an expense with empty employee_id
        self.documents_user.group_ids += self.env.ref('hr_expense.group_hr_expense_manager')

        attachment_txt.with_user(self.documents_user).document_hr_expense_create_hr_expense()
        expense = self.env['hr.expense'].search([('id', '=', attachment_txt.res_id)])
        self.assertFalse(expense.employee_id)

        # Finally, create an expense in a company that has no employees -> should create an expense with empty employee_id
        company = self.env['res.company'].create({
            'name': 'test company',
        })
        self.documents_user.company_ids += company
        attachment_txt = self._create_txt_attachment_for_documents_user(company=company)
        attachment_txt.with_user(self.documents_user).with_company(company).document_hr_expense_create_hr_expense()
        expense = self.env['hr.expense'].search([('id', '=', attachment_txt.res_id)])
        self.assertFalse(expense.employee_id)
