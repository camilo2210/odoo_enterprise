from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, RecordCapturer, tagged
from odoo.tools import mute_logger

from .test_documents_hr_common import TransactionCaseDocumentsHr


@tagged('test_document_bridge')
class TestCaseDocumentsBridgeHR(HttpCase, TransactionCaseDocumentsHr):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Employee (related to doc_user)',
            'user_id': cls.doc_user.id,
            'work_contact_id': cls.doc_user.partner_id.id,
            'wage': 1,
        })
        cls.folder = cls.env['documents.document'].create({
            'name': 'Test Document Folder',
            'type': 'folder',
        })

        cls.contract = cls.employee.version_id

    def test_document_count_with_archived_version(self):
        self.assertEqual(self.employee.document_count, 0)
        base_document_vals = {
            'partner_id': self.employee.work_contact_id.id,
            'owner_id': self.hr_manager.id,
            'raw': b'test content',
            'name': 'Test Document',
            'folder_id': self.folder.id,
            'res_model': 'hr.version',
        }
        original_version = self.employee.version_id
        self.env['documents.document'].sudo().create({**base_document_vals, 'res_id': original_version.id})
        self.employee.invalidate_recordset(['document_count'])
        self.assertEqual(self.employee.document_count, 1)

        # Simulate the signature of a new contract
        new_version = self.env['hr.version'].create({
            'name': 'new version',
            'employee_id': self.employee.id,
            'date_start': '2026-01-01',
            'date_version': '2026-01-01',
            'date_end': False,
        })
        original_version.active = False
        self.env['documents.document'].sudo().create({**base_document_vals, 'res_id': new_version.id})
        self.employee.invalidate_recordset(['document_count'])
        self.assertEqual(self.employee.document_count, 2)

    def test_document_count_of_employee_folder(self):
        """ The count must match what `action_open_documents` shows: the documents linked to the
        employee or to one of their versions, and everything stored under their folder. """
        employee_folder = self.employee.hr_employee_folder_id
        subfolder = self.env['documents.document'].sudo().create({
            'name': 'Employee subfolder',
            'type': 'folder',
            'folder_id': employee_folder.id,
        })
        base_document_vals = {'raw': b'test content', 'folder_id': self.folder.id}
        self.env['documents.document'].sudo().create([{
            **base_document_vals, 'name': 'In the employee folder', 'folder_id': employee_folder.id,
        }, {
            **base_document_vals, 'name': 'In a subfolder of the employee folder', 'folder_id': subfolder.id,
        }, {
            **base_document_vals, 'name': 'Linked to the employee',
            'res_model': 'hr.employee', 'res_id': self.employee.id,
        }, {
            **base_document_vals, 'name': 'Linked to a version of the employee',
            'res_model': 'hr.version', 'res_id': self.contract.id,
        }, {
            # Both in the folder and linked to the employee: counted once
            **base_document_vals, 'name': 'In the employee folder and linked to them',
            'folder_id': subfolder.id, 'res_model': 'hr.employee', 'res_id': self.employee.id,
        }])
        other_employee = self.env['hr.employee'].create({'name': 'Employee of another folder'})
        self.env['documents.document'].sudo().create({
            **base_document_vals,
            'name': "In the folder of the other employee",
            'folder_id': other_employee.hr_employee_folder_id.id,
        })

        employees = self.employee | other_employee
        employees.invalidate_recordset(['document_count'])
        # 4 queries: one for all leave_ids, payslips_ids, versions_ids, one for the _compute
        with self.assertQueryCount(4):
            self.assertEqual(
                employees.mapped('document_count'),  # Check batch compute
                [5, 1],
                "Each document is counted once, for the employee of its own folder"
            )

    def test_document_count_of_inaccessible_documents(self):
        """ A document is within the reach of the user, hence counted, if they can access it and
        either it is linked to the employee, or the whole folder chain from the employee folder
        down to it is accessible: the content of an unreachable folder appears in "Shared". """
        employee_folder = self.employee.hr_employee_folder_id
        no_access_vals = {
            'access_internal': 'none',
            'access_via_link': 'none',
            'is_access_via_link_hidden': True,
            'access_ids': False,  # do not inherit from the parent folder
        }
        subfolder = self.env['documents.document'].sudo().create({
            **no_access_vals,
            'name': 'Subfolder not shared with the HR user',
            'type': 'folder',
            'folder_id': employee_folder.id,
        })
        documents = self.env['documents.document'].sudo().create([{
            **no_access_vals, 'raw': b'test content',
            'name': 'In the employee folder', 'folder_id': employee_folder.id,
        }, {
            **no_access_vals, 'raw': b'test content',
            'name': 'Reachable only through the subfolder', 'folder_id': subfolder.id,
        }, {
            **no_access_vals, 'raw': b'test content', 'res_model': 'hr.employee', 'res_id': self.employee.id,
            'name': 'Linked to the employee, outside their folder', 'folder_id': self.folder.id,
        }, {
            **no_access_vals, 'raw': b'test content',
            'name': 'Linked to the employee, in the subfolder', 'folder_id': subfolder.id,
        }])
        documents[:2].write({'res_model': False, 'res_id': False})  # Un-linked from employee
        self.assertEqual((employee_folder | subfolder).with_user(self.hr_user).mapped('user_permission'),
                         ['none', 'none'], "The HR user must reach neither the folder nor its subfolder")
        self.assertEqual(documents.with_user(self.hr_user).mapped('user_permission'), ['none'] * 4,
                         "The HR user must reach none of the documents yet")

        employee = self.employee.with_user(self.hr_user)
        employee.invalidate_recordset(['document_count'])
        self.assertFalse(employee.document_count, "Nothing is within the reach of the HR user")

        # Sharing the documents themselves only brings the ones linked to the employee within reach
        documents.action_update_access_rights(partners={self.hr_user.partner_id: ('view', False)})
        employee.invalidate_recordset(['document_count'])
        self.assertEqual(employee.document_count, 2,
                         "The documents filed in an unreachable folder are still out of reach")

        # Sharing the employee folder brings its own content within reach
        employee_folder.action_update_access_rights(
            partners={self.hr_user.partner_id: ('view', False)}, no_propagation=True)
        employee.invalidate_recordset(['document_count'])
        self.assertEqual(employee.document_count, 3, "The content of the subfolder is still out of reach")

        # Sharing the subfolder brings its content within reach as well
        subfolder.action_update_access_rights(
            partners={self.hr_user.partner_id: ('view', False)}, no_propagation=True)
        employee.invalidate_recordset(['document_count'])
        self.assertEqual(employee.document_count, 4,
                         "The whole employee folder is within reach, its linked document counted once")

    def test_documents_hr_employees_folders_no_owner(self):
        # Document owner is the user that creates the document. But hr 'system' folders cannot be owned by anyone.
        public_user = self.env['res.users'].create({
            'name': 'Johnny Applicant',
            'login': 'applicant',
            'email': 'john.icant@example.com',
        })
        employee = self.env['hr.employee'].with_user(public_user).sudo().create({
            'name': 'Johnny Employee'
        })
        self.assertTrue(employee.hr_employee_folder_id, "The employee should have their folder.")
        self.assertFalse(employee.hr_employee_folder_id.owner_id, "Employee folders should not have an owner.")

    def test_documents_hr_employee_created_by_hr_manager(self):
        """Check that an HR manager can create employees for companies whose folders are partially set up."""
        new_company = self.env['res.company'].create({'name': "Company without document groups"})
        # State of any database upgraded without the upgrade scripts, or whose group was deleted.
        new_company.documents_hr_group_id = False
        self.hr_manager.company_ids |= new_company

        employee = self.env['hr.employee'].with_user(self.hr_manager).with_company(new_company).create({
            'name': "Employee of the HR manager",
        })

        self.assertTrue(new_company.documents_hr_group_id, "The HR documents group must have been created")
        self.assertIn(self.hr_manager, new_company.documents_hr_group_id.user_ids,
                      "HR users of the company must be seeded in the HR documents group")
        self.assertTrue(employee.hr_employee_folder_id, "The employee should have their folder.")
        self.assertFalse(employee.hr_employee_folder_id.sudo().owner_id,
                         "Employee folders must not be owned by the user who created the employee")

        # Idempotency: the group is not recreated for the next employee
        group = new_company.documents_hr_group_id
        self.env['hr.employee'].with_user(self.hr_manager).with_company(new_company).create({'name': "Second employee"})
        self.assertEqual(new_company.documents_hr_group_id, group)

    @mute_logger('odoo.sql_db')
    def test_documents_hr_employees_folder_is_required(self):
        """ The bridge is always enabled: the Employees folder of a company cannot be emptied. """
        with self.assertRaises(IntegrityError):
            self.env.company.documents_employee_folder_id = False
            self.env.flush_all()

    def test_documents_hr_no_employee_folder_for_archived_company(self):
        """Check that no employee folder will be created for new employees of an archived company."""
        archived_company = self.env['res.company'].create({'name': "Archived company"})
        self.assertTrue(archived_company.documents_employee_folder_id)
        archived_company.action_archive()

        employee = self.env['hr.employee'].with_company(archived_company).create({
            'name': "Employee of an archived company",
            'company_id': archived_company.id,
        })

        self.assertFalse(employee.hr_employee_folder_id,
                         "No folder should be generated for the employee of an archived company")

    def test_documents_hr_group_detached(self):
        """Check that a company whose HR documents group has been detached/unlinked gets a new one."""
        company = self.env.company
        old_group = company.documents_hr_group_id
        self.assertTrue(old_group, "The main company has the group shipped as data")
        self.assertIn(old_group, self.employee.hr_employee_folder_id.access_ids.group_id)

        company.documents_hr_group_id = False
        employee = self.env['hr.employee'].create({'name': "Employee of a new group"})

        new_group = company.documents_hr_group_id
        self.assertTrue(new_group, "A new group must have been created for the company")
        self.assertEqual(new_group.name, f"HR ({company.name})")
        self.assertIn(self.hr_user, new_group.user_ids, "HR users of the company must be seeded in the new group")
        self.assertIn(new_group, employee.hr_employee_folder_id.access_ids.group_id,
                      "The folder of the employee must be shared with the new group")
        self.assertNotIn(new_group, self.employee.hr_employee_folder_id.access_ids.group_id,
                         "Changing the group of a company does not affect the existing folders")

    def test_employee_subfolder_generation_renaming_and_access(self):
        # hr_employee_folder_id should have been created at employee creation
        self.assertEqual(self.employee.hr_employee_folder_id.name, self.employee.name,
                         "HR Employee Subfolder should have the same name as the employee.")
        self.employee.name = "Zator"
        self.assertEqual(self.employee.hr_employee_folder_id.name, "Zator",
                         "HR Employee Subfolder should be renamed when renaming the employee.")

        admin_user = self.env.ref('base.user_admin')
        # Test on new Company - HR Employee folder should be created on company create.
        # and a new employee should generate a subfolder for that employee inside the company's HR Employee folder.
        new_company = self.env['res.company'].with_user(admin_user).create({
            'name': 'New Company'
        })
        self.assertTrue(new_company.documents_employee_folder_id)
        # Newly created folder, created on company creation, should be in the company root.
        self.assertFalse(new_company.documents_employee_folder_id.owner_id)
        self.assertEqual(new_company.documents_employee_folder_id.user_folder_id, 'COMPANY')

        new_company_employee = self.env['hr.employee'].create({
            'name': 'New Company Employee',
            'user_id': self.doc_user_2.id,
            'company_id': new_company.id
        })
        self.assertTrue(new_company_employee.hr_employee_folder_id)
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_via_link, 'none')
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_internal, 'none')
        self.assertEqual(new_company_employee.hr_employee_folder_id.folder_id, new_company.documents_employee_folder_id)
        # Changing the folder of the company generates the folder of the employees that have none
        # (e.g. an employee archived when the module was installed) and moves the existing ones
        new_company_employee_bis = self.env['hr.employee'].create({
            'name': 'New Company Employee Bis',
            'company_id': new_company.id
        })
        new_company_employee_bis.hr_employee_folder_id = False
        new_company_folder = self.env['documents.document'].create({
            'name': 'New Company Employees',
            'type': 'folder',
            'company_id': new_company.id,
        })
        new_company.documents_employee_folder_id = new_company_folder
        self.assertEqual(new_company_employee_bis.hr_employee_folder_id.folder_id, new_company_folder,
                         "The employee without folder should have got one under the new folder.")
        self.assertEqual(new_company_employee.hr_employee_folder_id.folder_id, new_company_folder,
                         "The folder of the other employee should have been moved.")

        # Test changing settings for Documents HR Employee folder. All employee subfolders should follow.
        new_folder = self.env['documents.document'].create({
            'name': 'New folder',
            'type': 'folder'
        })
        self.env.company.documents_employee_folder_id = new_folder.id
        self.assertEqual(self.env.company.documents_employee_folder_id.access_via_link, 'none')
        self.assertEqual(self.env.company.documents_employee_folder_id.access_internal, 'none')
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_via_link, 'none')
        self.assertEqual(new_company_employee.hr_employee_folder_id.access_internal, 'none')
        self.assertEqual(self.employee.hr_employee_folder_id.folder_id.id, new_folder.id,
                         "Changing HR Employee folder target should be propagated to each employee subfolders.")
        self.assertEqual(self.employee.hr_employee_folder_id.access_via_link, 'none')
        self.assertEqual(self.employee.hr_employee_folder_id.access_internal, 'none')

        # Check access - only used for HR users - even employee should not have access to their "own" subfolder
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.doc_user_2).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.employee.user_id).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.employee.user_id).write({'name': "Test"})
        # Hr manager have access because added as edit member
        self.employee.hr_employee_folder_id.with_user(self.hr_manager).read(['name'])
        self.employee.hr_employee_folder_id.with_user(self.hr_manager).write({'name': "Test2"})
        self.employee.hr_employee_folder_id.access_ids = False
        # Hr user and HR manager should be able to view and edit but only using the access token
        # see @test_open_document_from_hr test method - If access to smart button and action, access to the records.
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_manager).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_user).read(['name'])
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_manager).write({'name': "Test2"})
        with self.assertRaises(AccessError):
            self.employee.hr_employee_folder_id.with_user(self.hr_user).write({'name': "Test"})

    def test_bridge_hr_settings_on_write(self):
        """
        Makes sure the settings apply their values when an ir_attachment is set as message_main_attachment_id
        on invoices.
        """
        attachment_txt_test = self.env['ir.attachment'].create({
            'raw': self.TEXT_RAW,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': 'hr.employee',
            'res_id': self.employee.id,
        })

        document = self.env['documents.document'].search([('attachment_id', '=', attachment_txt_test.id)])
        self.assertTrue(document.exists(), "There should be a new document created from the attachment")
        self.assertFalse(document.owner_id)
        self.assertFalse(document.partner_id)
        self.assertEqual(document.access_via_link, "none")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)

    def test_hr_employee_document_auto_created_not_shared_with_employee(self):
        """ Test that automatically created employee documents from attachment are not shared with the employee. """
        document = self.env['ir.attachment'].create({
            'name': 'test.txt',
            'mimetype': 'text/plain',
            'raw': self.TEXT_RAW,
            'res_model': 'hr.employee',
            'res_id': self.employee.id,
        }).document_ids
        self.assertTrue(document)
        self.assertEqual(document.with_user(self.employee.user_id).user_permission, 'none')

    def test_hr_employee_document_upload_not_shared_with_employee(self):
        """Test that uploaded hr.employee documents are not shared with the employee."""
        self.authenticate(self.hr_manager.login, self.hr_manager.login)
        with RecordCapturer(self.env['documents.document'], []) as capture:
            res = self.url_open(f'/documents/upload/{self.employee.hr_employee_folder_id.access_token}',
                data={
                    'csrf_token': self.csrf_token(),
                    'res_id': self.employee.id,
                    'res_model': 'hr.employee',
                },
                files={'ufile': ('hello.txt', b"Hello", 'text/plain')},
            )
            res.raise_for_status()
        document = capture.records.ensure_one()
        self.assertEqual(document.res_model, "hr.employee",
                         "The uploaded document is linked to the employee model")
        self.assertEqual(document.res_id, self.employee.id,
                         "The uploaded document is linked to the employee record")
        self.assertEqual(document.with_user(self.doc_user).user_permission, "none",
                         "The employee has no access to the uploaded document")
        self.assertEqual(document.with_user(self.hr_manager).user_permission, "edit",
                         "The HR manager has access to the uploaded document")

    def test_open_document_from_hr(self):
        """ Test that opening the document app from an employee (hr app) is opening only for hr users. """
        with self.assertRaises(AccessError):
            self.employee.with_user(self.doc_user_2).action_open_documents()
        action = self.employee.with_user(self.hr_user).action_open_documents()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], self.env['ir.actions.actions']._for_xml_id('documents.document_action_preference')['tag'])

    def test_raise_if_used_folder(self):
        """It shouldn't be possible to archive/delete a folder used by a company (see _unlink_except_company_folders)"""
        company_b = self.env['res.company'].create({'name': 'Company B'})
        root = self.env['documents.document'].create({'name': 'root', 'type': 'folder', 'access_internal': 'edit'})
        folder_parent = self.env['documents.document'].create(
            {'name': 'parent', 'type': 'folder', 'folder_id': root.id})
        folder_hr_employees2 = self.env['documents.document'].create({
            'name': 'Employees -  company 2', 'type': 'folder', 'folder_id': folder_parent.id, 'access_internal': 'none'})
        self.assertEqual(folder_parent.with_user(self.doc_user).user_permission, 'edit')
        self.assertEqual(folder_hr_employees2.with_user(self.doc_user).user_permission, 'none')
        with self.assertRaises(UserError,
                               msg="It should not be possible for non admin to archive the 'HR Employee' folder"):
            folder_hr_employees2.with_user(self.doc_user).action_archive()
        # It should be possible to archive a folder that is not the Employees folder of a company yet
        folder_hr_employees2.action_archive()
        folder_hr_employees2.action_unarchive()
        company_b.documents_employee_folder_id = folder_hr_employees2

        with self.assertRaises(UserError,
                               msg="It should not be possible to archive an used 'HR Employee' folder"):
            folder_hr_employees2.action_archive()
        with self.assertRaises(UserError,
                               msg="It should not be possible to archive an ancestor of the used 'HR' folder"):
            folder_parent.action_archive()
        with self.assertRaises(UserError,
                               msg="It should not be possible to unlink a 'HR Employee' folder"):
            folder_hr_employees2.unlink()
        with self.assertRaises(UserError,
                               msg="It should not be possible to delete an ancestor of the 'HR' folder"):
            folder_parent.unlink()
        self.assertTrue(folder_parent.exists())
        self.assertTrue(folder_hr_employees2.exists())

        with self.assertRaises(UserError,
                               msg="It should not be possible to delete an employee subfolder of the 'HR' Employee folder"):
            self.employee.hr_employee_folder_id.unlink()

    def test_portal_user_own_root_documents(self):
        """ Portal user (linked to employee!!) should be able to own root
        documents as they are now allowed to be set as employee related user
        and employee documents are store in their "my drive", and are,
        by definition, root documents"""
        employee_portal_user, normal_portal_user = self.env['res.users'].create([{
            'name': "Employee Portal User",
            'login': "employee_portal",
            'email': "employee_portal@yourcompany.com",
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]
        }, {
            'name': "Normal Portal User",
            'login': "normal_portal",
            'email': "normal_portal@yourcompany.com",
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]
        }])
        self.employee.user_id = employee_portal_user
        self.env['documents.document'].create({
            'name': 'test',
            'folder_id': False,
            'owner_id': employee_portal_user.id,
            'raw': 'test',
        })
        with self.assertRaises(ValidationError, msg="Portal users that are not linked to an employee cannot own root documents."):
            self.env['documents.document'].create({
                'name': 'test',
                'folder_id': False,
                'owner_id': normal_portal_user.id,
                'raw': 'test',
            })

    def test_contract_document_values(self):
        document = self.env['ir.attachment'].create({
            'raw': self.TEXT_RAW,
            'name': 'fileText_test.txt',
            'mimetype': 'text/plain',
            'res_model': self.contract._name,
            'res_id': self.contract.id,
        }).document_ids
        self.assertFalse(document.owner_id)
        self.assertFalse(document.partner_id)
        self.assertEqual(document.access_via_link, "none")
        self.assertEqual(document.access_internal, "none")
        self.assertTrue(document.is_access_via_link_hidden)

    def test_hr_contract_document_creation_permission_employee_only(self):
        """ Test that created hr.contract documents are only viewable by the employee and editable by hr managers. """
        self.check_document_creation_permission(self.contract)
