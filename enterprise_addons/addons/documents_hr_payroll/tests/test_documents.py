# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from contextlib import contextmanager
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError
from odoo.fields import Date

from odoo.addons.documents.models.documents_document import DocumentsDocument
from odoo.addons.documents.tests.test_documents_multipage import single_page_pdf
from odoo.addons.documents_hr.tests.test_documents_hr_common import TransactionCaseDocumentsHr
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests.common import RecordCapturer, tagged
from odoo.tools import BinaryBytes


@tagged('test_document_bridge')
class TestCaseDocumentsBridgeHR(TestPayslipBase, TransactionCaseDocumentsHr):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_us.ids))
        cls.env.user.company_id = cls.env.company.id

        cls.payroll_user = cls.env['res.users'].create({
            'name': "Hr payroll user test",
            'login': "hr_payroll_user_test",
            'email': "hr_payroll_user_test@yourcompany.com",
            'group_ids': [(6, 0, [cls.env.ref('hr_payroll.group_hr_payroll_user').id])],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Employee (related to doc_user_2)',
            'user_id': cls.doc_user_2.id,
            'work_contact_id': cls.doc_user_2.partner_id.id
        })
        cls.richard_emp.user_id = cls.doc_user
        cls.contract = cls.richard_emp.version_ids[0]
        cls.payslip = cls.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': cls.richard_emp.id,
            'version_id': cls.contract.id,
        })

    @contextmanager
    def _patch_declaration_mixin_methods(self, mail_template=False):
        """ Add on `hr.payslip` the `hr.payroll.declaration.mixin` methods used to post declarations.

        The declarations of the tests use `hr.payslip` as `res_model`, while the real ones use a
        declaration model (`l10n_be.281_10`, …), which implements that mixin.
        """
        payslip_model = self.env['hr.payslip'].pool['hr.payslip']
        with patch.object(
            payslip_model, "_get_posted_document_owner", lambda _s, employee: employee.user_id, create=True,
        ), patch.object(
            payslip_model, "_get_posted_mail_template", lambda _s: mail_template, create=True,
        ):
            yield

    def test_payslip_document_creation(self):
        # Set a different partner for the work_contact_id to verify that the partner of the employee user is used
        self.richard_emp.work_contact_id = self.doc_user.partner_id.copy()

        self.payslip.compute_sheet()
        self.payslip.with_context(payslip_generate_pdf=True, payslip_generate_pdf_direct=True).action_payslip_done()

        attachment = self.env['ir.attachment'].search([('res_model', '=', self.payslip._name), ('res_id', '=', self.payslip.id)])
        self.assertTrue(attachment, "Validating a payslip should have created an attachment")

        document = self.env['documents.document'].search([('attachment_id', '=', attachment.id)])
        self.assertTrue(document, "There should be a new document created from the attachment")
        self.assertFalse(document.owner_id)
        self.assertEqual(document.folder_id, self.richard_emp.hr_employee_payroll_folder_id, "The document should have been created in the employee's Payroll folder")
        self.assertEqual(document.access_via_link, "view")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)
        self.assertEqual(len(document.shortcut_ids), 1)
        self.assertEqual(document.shortcut_ids.with_user(self.richard_emp.user_id).user_folder_id, "MY", "A shortcut should have been created in the employee's My Drive")
        # Only one access record, with the owner's partner. No one else than the employee itself should have access to the document.
        self.assertEqual(
            {(a.partner_id, a.group_id): a.role for a in document.access_ids},
            {
                (self.richard_emp.user_id.partner_id, self.env["res.group.functional"]): "view",
                (self.env["res.partner"], self.richard_emp.company_id.documents_hr_payroll_group_id): "edit",
             },
            "Only the Payroll group should have access (write)"
        )
        self.assertEqual(document.with_user(self.richard_emp.user_id).user_permission, "view")
        self.check_document_no_access(document, self.doc_user_2)
        self.check_document_no_access(document, self.document_manager)
        self.check_document_no_access(document, self.payroll_user)

    def test_documents_hr_payroll_employee_folders(self):
        """Check that the employee folder and its Payroll subfolder are generated without owner."""
        employee = self.env['hr.employee'].create({'name': "Employee of the payroll folder test"})
        employee_folders = employee.hr_employee_folder_id | employee.hr_employee_payroll_folder_id
        self.assertEqual(len(employee_folders), 2, "Employee should have their folder and payroll subfolder.")
        self.assertFalse(employee_folders.owner_id, "Employee folders should not have an owner.")
        self.assertEqual(employee.hr_employee_payroll_folder_id.folder_id, employee.hr_employee_folder_id)

    def test_documents_hr_payroll_generate_payroll_folder_only(self):
        """Check the generation of the Payroll folder alone, the company group being unset."""
        employee = self.env['hr.employee'].create({'name': "Employee without payroll folder"})
        employee.hr_employee_payroll_folder_id = False
        self.env.company.documents_hr_group_id = False
        self.env.company.documents_hr_payroll_group_id = False

        employee._generate_employee_documents_folders()

        self.assertTrue(self.env.company.documents_hr_payroll_group_id)
        self.assertTrue(employee.hr_employee_payroll_folder_id, "The Payroll folder must have been created")
        self.assertEqual(employee.hr_employee_payroll_folder_id.access_ids.group_id,
                         self.env.company.documents_hr_payroll_group_id)

    def test_documents_hr_payroll_no_folder_without_employee_folder(self):
        """Check that no Payroll folder is created at the root for an employee without folder."""
        archived_company = self.env['res.company'].create({'name': "Archived company"})
        archived_company.action_archive()

        employee = self.env['hr.employee'].with_company(archived_company).create({
            'name': "Employee of an archived company",
            'company_id': archived_company.id,
        })

        self.assertFalse(employee.hr_employee_folder_id)
        self.assertFalse(employee.hr_employee_payroll_folder_id,
                         "The Payroll folder must not be created without the folder containing it")

    def test_documents_hr_payroll_folder_cannot_be_deleted(self):
        """Check that the Payroll folder of an employee is protected, as their employee folder."""
        with self.assertRaises(UserError, msg="It should not be possible to delete a 'Payroll' folder"):
            self.richard_emp.hr_employee_payroll_folder_id.unlink()

    def test_documents_hr_payroll_folder_generated_by_hr_manager(self):
        """Check that an HR user without payroll access still generates the Payroll folder."""
        # This test class works in `company_us`, of which the HR manager is not a member: the
        # employee is created in their own company (`with_company` keeps `company_us` allowed).
        employee = self.env['hr.employee'].with_user(self.hr_manager).with_context(
            allowed_company_ids=self.hr_manager.company_ids.ids,
        ).create({
            'name': "Employee of the HR manager",
        })
        self.assertTrue(employee.sudo().hr_employee_payroll_folder_id,
                        "The Payroll folder must be created whoever creates the employee")

    def test_payslip_document_access_of_payroll_group(self):
        """Check that Payroll users can edit generated payslips, other HR users cannot. """
        company = self.richard_emp.company_id
        self.payroll_user.company_ids |= company
        self.hr_user.company_ids |= company
        # Group members are added at group creation (install/upgrade), the users above are newer.
        company.documents_hr_payroll_group_id.sudo().user_ids |= company._get_documents_hr_payroll_group_users()
        self.assertIn(self.payroll_user, company.documents_hr_payroll_group_id.user_ids,
                      "Payroll users must be members of the company payroll documents group")
        self.assertNotIn(self.hr_user, company.documents_hr_payroll_group_id.user_ids,
                         "HR users must not be members of the company payroll documents group")

        self.payslip.compute_sheet()
        self.payslip.with_context(payslip_generate_pdf=True, payslip_generate_pdf_direct=True).action_payslip_done()
        document = self.env['documents.document'].search([
            ('res_model', '=', 'hr.payslip'), ('res_id', '=', self.payslip.id), ('shortcut_document_id', '=', False)])

        self.assertEqual(document.with_user(self.payroll_user).user_permission, 'edit',
                         "Payroll group members must be able to manage the payslips")
        self.check_document_no_access(document, self.hr_user)

    def test_document_count_of_payslip_documents(self):
        """Check that the payslip documents are counted once, being both filed in the Payroll folder
        of the employee and linked to their payslip."""
        company = self.richard_emp.company_id
        self.payroll_user.company_ids |= company
        company.documents_hr_payroll_group_id.sudo().user_ids |= company._get_documents_hr_payroll_group_users()

        self.payslip.compute_sheet()
        self.payslip.with_context(payslip_generate_pdf=True, payslip_generate_pdf_direct=True).action_payslip_done()

        payslip_documents = self.env['documents.document'].with_user(self.payroll_user).search([
            ('res_model', '=', 'hr.payslip'), ('res_id', '=', self.payslip.id)])
        self.assertTrue(payslip_documents, "The payslip documents must be accessible to the payroll group")

        employee = self.richard_emp.with_user(self.payroll_user)
        employee.invalidate_recordset(['document_count'])
        self.assertEqual(
            employee.document_count,
            1,
            "The payslip document in the Payroll folder and linked should only be counted once, "
            "and the shortcut not at all."
        )

    def test_payslip_document_creation_generates_missing_folders(self):
        """Check that the employee folders are generated on the fly if necessary, when generating the
        payslip PDF, instead of filing the payslip in a root folder."""
        self.richard_emp.hr_employee_folder_id = False
        self.richard_emp.hr_employee_payroll_folder_id = False
        self.assertFalse(self.payslip._check_create_documents())

        self.payslip.compute_sheet()
        self.payslip.with_context(payslip_generate_pdf=True, payslip_generate_pdf_direct=True).action_payslip_done()

        payroll_folder = self.richard_emp.hr_employee_payroll_folder_id
        self.assertTrue(payroll_folder, "The folders of the employee must have been generated")
        self.assertEqual(payroll_folder.folder_id, self.richard_emp.hr_employee_folder_id)
        document = self.env['documents.document'].search([
            ('res_model', '=', 'hr.payslip'), ('res_id', '=', self.payslip.id), ('shortcut_document_id', '=', False)])
        self.assertEqual(document.folder_id, payroll_folder,
                         "The payslip must be filed in the Payroll folder of its employee")

    def test_hr_payroll_employee_declaration_generates_missing_folders(self):
        """Check that employee folders are generated on the fly if necessary when posting a declaration. """
        self.employee.hr_employee_folder_id = False
        self.employee.hr_employee_payroll_folder_id = False
        declaration = self.env['hr.payroll.employee.declaration'].create({
            'res_model': 'hr.payslip',
            'res_id': self.payslip.id,
            'employee_id': self.employee.id,
            'pdf_file': BinaryBytes(single_page_pdf),
            'pdf_filename': 'Test Declaration.pdf',
            'state': 'pdf_to_post',
        })
        with self._patch_declaration_mixin_methods():
            declaration._post_pdf()

        payroll_folder = self.employee.hr_employee_payroll_folder_id
        self.assertTrue(payroll_folder, "The folders of the employee must have been generated")
        self.assertEqual(payroll_folder.folder_id, self.employee.hr_employee_folder_id)
        self.assertEqual(declaration.document_id.folder_id, payroll_folder,
                         "The declaration must be posted in the Payroll folder of its employee")

    def test_hr_payroll_employee_declaration_document_creation_simple(self):
        """Check that the employee is the owner of the declarations and that nobody else has access."""
        declaration = self.env['hr.payroll.employee.declaration'].create({
            'res_model': 'hr.payslip',
            'res_id': self.payslip.id,
            'employee_id': self.employee.id,
            'pdf_file': BinaryBytes(single_page_pdf),
            'pdf_filename': 'Test Declaration.pdf',
            'state': 'pdf_to_post',
        })

        mail_template = self.env.ref('documents_hr_payroll.mail_template_new_declaration', raise_if_not_found=False)
        with self._patch_declaration_mixin_methods(mail_template):
            declaration._post_pdf()

        document = declaration.document_id
        self.assertTrue(document, "A document should have been created")

        # Folder structure checks
        payroll_folder = document.folder_id
        employee_folder = self.employee.hr_employee_folder_id
        root_folder = employee_folder.folder_id

        self.assertEqual(document.name, 'Test Declaration.pdf')
        self.assertFalse(document.owner_id)
        self.assertEqual(len(document.shortcut_ids), 1)
        self.assertEqual(document.shortcut_ids.owner_id, self.employee.user_id)
        self.assertFalse(document.shortcut_ids.folder_id, "Shortcut must be inside employee's My Drive")

        self.assertTrue(payroll_folder, "Document must be inside the Payroll folder")
        self.assertEqual(payroll_folder.name, "Payroll")
        self.assertEqual(payroll_folder.folder_id, employee_folder, "Payroll folder must be inside the employee folder")

        self.assertEqual(employee_folder.name, self.employee.name)
        self.assertEqual(root_folder.name, f"Employees - {self.env.company.name}")

        # Access rights checks
        self.assertEqual(
            set(document.access_ids.mapped(lambda a: (a.partner_id, a.group_id, a.role))),
            {
                (self.employee.user_partner_id, self.env["res.group.functional"], 'view'),
                (self.env["res.partner"], self.env.company.documents_hr_payroll_group_id, 'edit'),
             }
        )
        self.assertEqual(document.access_via_link, "view", "Should allow public viewing via link")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)
        self.assertTrue(document.access_token, "An access token must be generated")

        self.check_document_no_access(document, self.doc_user)
        self.check_document_no_access(document, self.document_manager)
        self.check_document_no_access(document, self.payroll_user)

        # Email checks
        mail = self.env['mail.mail'].search([
            ('res_id', '=', declaration.id),
            ('model', '=', declaration._name)
        ])

        self.assertTrue(mail, "Email should have been generated")
        self.assertIn(
            document.access_url,
            mail.body_html,
            "The login-free link must be present in the email body"
        )

    def test_hr_payroll_employee_declaration_batch_without_payroll_folder(self):
        """Check that a batch whose first declaration has no Payroll folder yet posts every
        declaration in the folder of its own employee, and not in the one of another."""
        employee_without_folder = self.env['hr.employee'].create({
            'name': "Employee without Payroll folder",
        })
        employee_without_folder.hr_employee_payroll_folder_id = False

        declarations = self.env['hr.payroll.employee.declaration'].create([{
            'res_model': 'hr.payslip',
            'res_id': self.payslip.id,
            'employee_id': employee.id,
            'pdf_file': BinaryBytes(single_page_pdf),
            'pdf_filename': f'Test Declaration {employee.name}.pdf',
        } for employee in (employee_without_folder, self.richard_emp)])
        generated, posted = declarations
        declarations.action_post_in_documents()

        with self._patch_declaration_mixin_methods(), RecordCapturer(self.env['documents.document']) as capture:
            self.env['hr.payslip']._cron_generate_pdf()

        new_folders = capture.records.filtered(lambda d: d.type == 'folder')
        expected_created_payroll_folder = generated.document_id.folder_id
        self.assertIn(generated.document_id.folder_id, new_folders)
        self.assertEqual(expected_created_payroll_folder, employee_without_folder.hr_employee_payroll_folder_id,
                         "The Payroll folder of the employee that had none must have been generated to receive it")
        self.assertEqual(posted.document_id.folder_id, self.richard_emp.hr_employee_payroll_folder_id,
                         "The other declaration of the batch must be posted in the folder of its own employee")

    @patch.object(DocumentsDocument, '_get_is_multipage', lambda __: False)
    def test_hr_payroll_employee_declaration_overwrite(self):
        """
        Test that if a document already exists for a declaration, it is overwritten and not duplicated
        when _post_pdf is called multiple times.
        """
        declaration = self.env['hr.payroll.employee.declaration'].create({
            'res_model': 'hr.payslip',
            'res_id': self.payslip.id,
            'employee_id': self.employee.id,
            'pdf_file': BinaryBytes(b'Version 1'),
            'pdf_filename': 'Test Declaration.pdf',
            'state': 'pdf_to_post',
        })

        mail_template = self.env.ref('documents_hr_payroll.mail_template_new_declaration', raise_if_not_found=False)
        # Post initial document
        with self._patch_declaration_mixin_methods(mail_template):
            declaration._post_pdf()

        first_doc_id = declaration.document_id.id
        self.assertEqual(bytes(declaration.document_id.raw), b'Version 1')

        # Update the content and post again
        declaration.write({'pdf_file': BinaryBytes(b'Version 2')})
        with self._patch_declaration_mixin_methods(mail_template):
            declaration._post_pdf()

        # Assertions
        # Ensure the document ID remained the same (no new record created)
        self.assertEqual(declaration.document_id.id, first_doc_id, "Should overwrite existing record")
        # Ensure the content was actually updated
        self.assertEqual(bytes(declaration.document_id.raw), b'Version 2', "Content should be updated")

        # Ensure only one document exists in that folder with that name
        doc_count = self.env['documents.document'].search_count([
            ('name', '=', 'Test Declaration.pdf'),
            ('folder_id', '=', declaration.document_id.folder_id.id)
        ])
        self.assertEqual(doc_count, 1, "There should not be duplicate documents")

    def test_payslip_document_creation_with_no_partner(self):
        """Check that the payslip document is created when the employee has no partner."""
        # Ensure the employee has no partner
        self.richard_emp.user_id = False
        self.richard_emp.user_id.partner_id = False
        self.richard_emp.work_contact_id = False

        payslip = self.payslip
        payslip.compute_sheet()
        payslip.with_context(payslip_generate_pdf=True).action_payslip_done()

        document = self.env['documents.document'].search([('res_model', '=', payslip._name), ('res_id', '=', payslip.id)])
        self.assertTrue(document, "A document will be created if the employee has no partner.")

    def test_payslip_document_creation_with_several_payslips(self):
        """Check that the payslip documents are created when the cron is run on several payslips."""
        contract_jul = self.jules_emp.create_version({
            'date_version': Date.to_date('2018-01-01'),
            'contract_date_start': Date.to_date('2018-01-01'),
            'contract_date_end': Date.today() + relativedelta(years=2),
            'date_end': Date.today() + relativedelta(years=2),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'structure_type_id': self.structure_type.id,
        })

        payslip_jul = self.env['hr.payslip'].create({
            'employee_id': self.jules_emp.id,
            'version_id': contract_jul.id,
        })
        payslip_ric = self.payslip
        payslip_emp_3 = payslip_ric.copy()
        payslip_emp_4 = payslip_ric.copy()
        payslip_emp_5 = payslip_ric.copy()
        payslip_emp_6 = payslip_ric.copy()
        payslips = payslip_jul + payslip_ric + payslip_emp_3 + payslip_emp_4 + payslip_emp_5 + payslip_emp_6

        payslips.compute_sheet()
        payslips.with_context(payslip_generate_pdf=True).action_payslip_done()
        self.assertTrue(payslip_jul.queued_for_pdf)
        self.assertTrue(payslip_ric.queued_for_pdf)

        self.env['hr.payslip']._cron_generate_pdf()

        # Check if the documents are created
        documents = self.env['documents.document'].search([('res_model', '=', payslips._name), ('res_id', 'in', payslips.ids)])
        self.assertEqual(len(documents), 11, "Expected 6 payslips and 5 shortcuts")
        without_shortcut = documents.filtered(lambda d: not d.shortcut_document_id and not d.shortcut_ids)
        self.assertEqual(len(without_shortcut), 1)
        self.assertEqual(without_shortcut.res_id, payslip_jul.id, "Jules has no My Drive for a shortcut")
        self.assertEqual(documents.shortcut_ids, documents.filtered('shortcut_document_id'))

    def test_payslip_document_unlink_delete_document(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
            'structure_id': self.developer_pay_structure.id,
        })

        payslip_run._generate_payslips()
        payslip_run.with_context(payslip_generate_pdf=True).action_validate()

        self.env['hr.payslip']._cron_generate_pdf()

        payslip = payslip_run.slip_ids[0]

        # Check if the document are created
        documents = self.env['documents.document'].search([('res_model', '=', payslip._name), ('res_id', 'in', payslip.ids)])
        shortcut = documents.filtered('shortcut_document_id')
        source = documents - shortcut
        self.assertEqual(len(source), 1)
        self.assertEqual(shortcut.shortcut_document_id, source)

        payslip_ids = payslip.ids

        payslip.action_payslip_draft()
        payslip_run.action_draft()
        payslip_run.unlink()

        documents = self.env['documents.document'].search([('res_model', '=', 'hr.payslip'), ('res_id', 'in', payslip_ids)])
        self.assertEqual(len(documents), 0)
