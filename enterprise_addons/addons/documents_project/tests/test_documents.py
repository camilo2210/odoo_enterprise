from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tests.common import Command, users

from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments
from odoo.addons.project.tests.test_project_base import TestProjectCommon

from odoo.addons.base.tests.files import GIF_RAW

TEXT_RAW = b"workflow bridge project"


class TestDocumentsBridgeProject(TestProjectCommon, TransactionCaseDocuments):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_txt_2 = cls.env['documents.document'].create({
            'raw': TEXT_RAW,
            'name': 'file2.txt',
            'mimetype': 'text/plain',
            'folder_id': cls.folder_a_a.id,
        })
        cls.pro_admin = cls.env['res.users'].create({
            'name': 'Project Admin',
            'login': 'proj_admin',
            'email': 'proj_admin@example.com',
            'group_ids': [(4, cls.env.ref('project.group_project_manager').id)],
        })

    def test_archive_folder_on_projects_unlinked(self):
        """
        The project folder should be archived when that project is unlinked, an archived project
        still counting as a related project.
        """
        folder_1, folder_2, folder_3, folder_4, folder_5 = self.env['documents.document'].create(
            [{'name': f'F{i}', 'type': 'folder'} for i in range(5)]
        )

        project_1, project_2, project_3 = self.env['project.project'].create([
            {'name': f'p{i}', 'documents_folder_id': folder.id}
            for i, folder in enumerate((folder_1, folder_2, folder_3))
        ])
        archived_project = self.env['project.project'].create({
            'name': 'p_archived',
            'documents_folder_id': folder_5.id,
            'active': False,
        })

        cases = [
            (
                project_1,
                folder_2 | folder_3 | folder_4 | folder_5,
                folder_1,
            ), (
                project_2 | project_3,
                folder_4 | folder_5,
                folder_1 | folder_2 | folder_3,
            ),
        ]

        count_start = self.env['documents.document'].search_count([('active', '=', True)])

        for projects_to_unlink, active_folders, inactive_folders in cases:
            with self.subTest(projects_to_unlink=projects_to_unlink, active_folders=active_folders, inactive_folders=inactive_folders):
                projects_to_unlink.unlink()
                self.assertTrue(all(active_folders.mapped('active')))
                self.assertFalse(any(inactive_folders.mapped('active')))

        self.assertTrue(
            archived_project.documents_folder_id.active,
            "The folder of an archived project should be kept, no matter which other projects are unlinked")

        count_end = self.env['documents.document'].search_count([('active', '=', True)])
        self.assertEqual(count_end, count_start - 3)

    def test_bridge_parent_folder(self):
        """
        Tests the "Parent Folder" setting
        """
        parent_folder = self.env.company.documents_project_folder_id
        self.assertEqual(self.project_pigs.documents_folder_id.folder_id, parent_folder, "The folder of the project should be a child of the 'Projects' folder.")

    def test_project_folder_creation(self):
        project = self.env['project.project'].create({
            'name': 'Project',
        })
        self.assertTrue(project.documents_folder_id, "A folder should be created for the project")

    def test_change_visibility_updates_document_access(self):
        """Changing project visibility updates document access when its folder
        contains a shortcut."""
        folder = self.project_pigs.documents_folder_id
        document = self.env['documents.document'].create({
            'raw': TEXT_RAW,
            'name': 'in_folder.txt',
            'mimetype': 'text/plain',
            'folder_id': folder.id,
        })
        shortcut = self.document_txt_2.action_create_shortcut(location_user_folder_id=str(folder.id))
        self.assertEqual(shortcut.folder_id, folder)
        self.assertEqual(folder.access_internal, 'edit')
        self.assertEqual(document.access_internal, 'edit')
        self.assertEqual(shortcut.access_internal, 'view')
        self.assertEqual(self.document_txt_2.access_internal, 'view')

        self.project_pigs.privacy_visibility = 'followers'
        self.assertEqual(folder.access_internal, 'none')
        self.assertEqual(document.access_internal, 'none')
        self.assertEqual(shortcut.access_internal, 'view')
        self.assertEqual(self.document_txt_2.access_internal, 'view')

    def test_project_task_access_document(self):
        """
        Tests that 'MissingRecord' error should not be raised when trying to switch
        folder for a non-existing document.

        - The 'active_id' here is the 'id' of a non-existing document.
        - We then try to access 'All' folder by calling the 'search_panel_select_range'
            method. We should be able to access the folder.
        """
        missing_id = self.env['documents.document'].search([], order='id DESC', limit=1).id + 1
        result = self.env['documents.document'].with_context(
            active_id=missing_id, active_model='project.task').search_panel_select_range('user_folder_id')
        self.assertTrue(result)

    def test_copy_project(self):
        """
        When duplicating a project, there should be exactly one copy of the folder linked to the project.
        If there is the `no_create_folder` context key, then the folder should not be copied (note that in normal flows,
        when this context key is used, it is expected that a folder will be copied/created manually, so that we don't
        end up with a project having the documents feature enabled but no folder).
        """
        last_folder_id = self.env['documents.document'].search([('type', '=', 'folder')], order='id desc', limit=1).id
        self.project_pigs.copy()
        new_folder = self.env['documents.document'].search([('type', '=', 'folder'), ('id', '>', last_folder_id)])
        self.assertEqual(len(new_folder), 1, "There should only be one new folder created.")
        self.project_goats.with_context(no_create_folder=True).copy()
        self.assertEqual(self.env['documents.document'].search_count(
            [('type', '=', 'folder'), ('id', '>', new_folder.id)], limit=1),
            0,
            "There should be no new folder created."
        )

    def test_project_change_visibility(self):
        """
        When changing the visibility of a project, the access rights on the folder should be updated accordingly.
        """
        # Remove project folder access rights to test properly
        self.env.ref('documents_project.document_project_folder').access_ids.unlink()
        customer = self.user_employee.partner_id
        project = self.env['project.project'].create({
            'partner_id': customer.id,
            'name': 'Test Project',
            'privacy_visibility': 'followers',
        })
        folder = project.documents_folder_id
        self.assertEqual(folder.access_internal, 'none', "The folder should not have internal access for 'followers' visibility.")
        # No followers at this point
        self.assertFalse(project.message_partner_ids)
        self.assertFalse(folder.access_ids.partner_id, "Nobody should have access to the folder as no followers of the project exist.")
        project.privacy_visibility = 'employees'
        self.assertEqual(folder.access_internal, 'edit', "The folder should be editable for 'employees' visibility.")
        self.assertFalse(folder.access_ids.partner_id, "Nobody should have access to the folder as no followers of the project exist.")
        project.privacy_visibility = 'invited_users'
        self.assertEqual(folder.access_internal, 'none', "The folder should not be accessible for 'invited_users' visibility.")
        self.assertEqual(
            folder.access_ids.partner_id,
            project.message_partner_ids.filtered(lambda p: not p.partner_share),
            "Followers are not synced properly with the documents folder for the project with the visibility 'invited_users'."
        )
        project.privacy_visibility = 'portal'
        self.assertEqual(folder.access_internal, 'edit', "The folder should have internal access for 'portal' visibility.")
        # Portal users are never added to folder access; internal users access via access_internal='edit'
        self.assertFalse(folder.access_ids.partner_id, "No partner should have explicit access in 'portal' visibility.")
        extra_member = self.user_projectuser.partner_id
        project.message_subscribe(partner_ids=extra_member.ids)

        # Test that the followers sync logic is only executed when privacy visibility is changed.
        folder.access_internal = 'view'  # force other value than synced value
        project.privacy_visibility = 'portal'
        self.assertEqual(
            folder.access_internal,
            'view',
            "The access rights for the documents shouldn't be synced when the privacy visibility is not changed."
        )

    def test_project_folder_inherits_actions_from_parent(self):
        """
        The project folders should inherit the embedded actions of the 'Projects' folder on creation.
        """
        project_folder = self.env.ref('documents_project.document_project_folder')
        # Remove all the embedded actions from the 'Projects' folder to test properly
        self.env['ir.embedded.actions'].sudo().search(
            domain=Domain.AND([
                self.env['ir.embedded.actions']._get_documents_embed_base_domain(),
                [('parent_res_id', '=', project_folder.id)],
            ])
        ).unlink()
        folder_embedded_actions = self.env['documents.document']._get_folder_embedded_actions(project_folder.ids)
        self.assertFalse(
            folder_embedded_actions.get(project_folder.id),
            "The 'Project' folder should not have any embedded actions."
        )

        # Embed two actions in the 'Projects' folder, and check that the project folder inherits them
        # We restrict one action to the 'documents_manager' group, which 'proj_admin' does not have.
        restricted_action = self.server_action.copy({
            'name': "Copy of Test Action",
            'group_ids': [self.env.ref('documents.group_documents_manager').ids],
        })
        self.env['documents.document'].action_folder_embed_action(project_folder.id, self.server_action.id)
        self.env['documents.document'].action_folder_embed_action(project_folder.id, restricted_action.id)

        # Create as a user who doesn't have the restricted action's group
        self.assertFalse(self.pro_admin.has_group('documents.group_documents_manager'))
        project = self.env['project.project'].with_user(self.pro_admin).create({'name': "Test Project"})

        folder_embedded_actions = self.env['documents.document'].sudo()._get_folder_embedded_actions((project_folder + project.documents_folder_id).ids)
        self.assertTrue(len(folder_embedded_actions.get(project_folder.id, [])) == 2, "The 'Projects' folder should have embedded actions.")
        self.assertEqual(
            folder_embedded_actions.get(project_folder.id, self.env['ir.embedded.actions']).action_id,
            folder_embedded_actions.get(project.documents_folder_id.id, self.env['ir.embedded.actions']).action_id,
            "The newly created project folder should inherit the embedded actions of the 'Projects' folder (even group-restricted ones)."
        )

    @users('proj_admin')
    def test_rename_project(self):
        """
        When renaming a project, the corresponding folder should be renamed as well.
        Even when the user does not have write access on the folder, the project should be able to rename it.
        """
        new_name = 'New Name'
        self.project_pigs.with_user(self.env.user).name = new_name
        self.assertEqual(self.project_pigs.documents_folder_id.name, new_name, "The folder should have been renamed along with the project.")

    def test_delete_project_folder(self):
        """
        It should not be possible to delete the "Projects" folder.
        """
        project_folder = self.env.ref('documents_project.document_project_folder')
        with self.assertRaises(UserError, msg="It should not be possible to delete the 'Projects' folder"):
            project_folder.unlink()

        current = project_folder
        for i in range(3):
            current.folder_id = self.env['documents.document'].create({
                "name": f"Ancestor Test {i}",
                "type": "folder",
            })
            current = current.folder_id

        with self.assertRaises(UserError, msg="It should not be possible to delete an ancestor of the 'Projects' folder"):
            current.unlink()

        # But it shouldn't interfere with legit deletion/archiving
        project_folder.action_update_access_rights(
            access_internal='none', access_via_link='none',
            partners={self.doc_user.partner_id.id: (False, False)})
        project_folder.invalidate_recordset(fnames=['parent_path'])
        self.document_txt.with_user(self.doc_user).action_archive()
        self.assertFalse(self.document_txt.active)
        self.document_txt.with_user(self.doc_user).unlink()
        self.assertFalse(self.document_txt.exists())

    def test_changing_project_folder_moves_documents(self):
        """
        When a project folder changes, move documents.
        """
        project = self.env['project.project'].create({'name': 'Project'})
        project_document, other_folder = self.env['documents.document'].create([{
            'name': 'Test project request',
            'folder_id':  project.documents_folder_id.id,
            'res_model': 'project.project',
            'res_id': project.id,
            'raw': 'test',
        }, {
            'name': 'Other Folder',
            'type': 'folder',
            'folder_id': self.env.ref('documents_project.document_project_folder').id,
        }])
        project.invalidate_recordset()
        self.assertEqual(project_document, project.document_ids)
        project.documents_folder_id = other_folder
        self.assertEqual(project_document.folder_id, other_folder)
        self.assertEqual(project_document, project.document_ids)

    def test_delete_folder_used_by_project(self):
        """
        It shouldn't be possible to delete a folder that is used by one or multiple projects.
        """
        project = self.env['project.project'].create({
            'name': "Test",
        })
        with self.assertRaises(UserError):
            project.documents_folder_id.unlink()

        project_1, project_2 = self.env['project.project'].create([{
            'name': f"Test Project {i}",
        } for i in range(2)])
        (project_1 | project_2).documents_folder_id.folder_id = parent_folder = self.env['documents.document'].create({
            'name': "Test Folder",
            'type': 'folder',
        })
        with self.assertRaises(UserError, msg="It shouldn't be possible to delete a folder that is used by one or multiple projects."):
            parent_folder.unlink()

    def test_add_attachment_to_project_folder_id(self):
        project = self.env['project.project'].create({'name': "Test Project"})
        self.assertTrue(project.documents_folder_id)
        task = self.env['project.task'].create({'name': "Test Task", 'project_id': project.id})
        project_attachment, task_attachment = self.env['ir.attachment'].create([
            {"name": "project_image.png", "raw": GIF_RAW, "res_model": "project.project", "res_id": project.id},
            {"name": "task_image.png", "raw": GIF_RAW, "res_model": "project.task", "res_id": task.id},
        ])
        for attachment in (project_attachment, task_attachment):
            self.assertEqual(attachment.get_documents_operation_add_destination(), {
                'destination': str(project.documents_folder_id.id),
                'display_name': project.documents_folder_id.display_name,
            })

        # Ensuring that the bridge between project.tasks and documents.document is working
        documents = task_attachment.document_ids
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents.res_model, "project.task")
        self.assertEqual(documents.res_id, task.id)

    def test_task_follower_can_read_attachment_without_document(self):
        user = self.user_projectuser
        project = self.env['project.project'].create({
            'name': "Private Project",
            'privacy_visibility': 'followers',
            'task_ids': [Command.create({'name': "Followed Task"})],
        })
        task = project.task_ids
        task.message_subscribe(partner_ids=user.partner_id.ids)
        attachment = self.env['ir.attachment'].with_context(no_document=True).create({
            'name': "Legacy attachment",
            'raw': b"attachment content",
            'res_model': task._name,
            'res_id': task.id,
        })

        self.assertFalse(attachment.document_ids)
        self.assertTrue(task.with_user(user).has_access('read'))
        self.assertFalse(project.with_user(user).has_access('read'))
        self.env.invalidate_all()
        self.assertFalse(attachment.with_user(user).linked_document_id)

    def test_project_copy_includes_linked_documents(self):
        """
        Test that copying a project also copies its linked document.
        Steps:
        1. Link a document to the project (set folder and res_id).
        2. Copy the project.
        3. Check that the copied project has one linked document.
        """
        self.document_txt_2.write({
            'folder_id': self.project_pigs.documents_folder_id.id,
            'res_model': 'project.project',
            'res_id': self.project_pigs.id,
        })
        copied_project_documents = self.project_pigs.copy().document_ids
        self.assertEqual(
            len(copied_project_documents), 1,
            "The copied project should have one document copied."
        )

    def test_unlink_project_task(self):
        project = self.env["project.project"].create(
            {"name": "Test Project", "tasks": [Command.create({"name": "Test Task"})]}
        )
        self.assertTrue(project.documents_folder_id)
        task = project.tasks[0]
        doc = self.env["documents.document"].create(
            {
                "name": "task_image.png",
                "raw": GIF_RAW,
                "res_model": "project.task",
                "res_id": task.id,
            }
        )
        self.assertEqual(doc.attachment_id.res_id, task.id)
        self.assertEqual(doc.attachment_id.res_model, 'project.task')

        task.unlink()

        self.assertTrue(doc.exists())
        self.assertFalse(doc.active)
        self.assertFalse(doc.res_id)
        self.assertFalse(doc.res_model)
        self.assertEqual(doc.attachment_id.res_id, doc.id)
        self.assertEqual(doc.attachment_id.res_model, 'documents.document')

    def test_project_document_unarchive_on_revert(self):
        """ Ensure project documents are unarchived when a project is reverted
        Steps:
            1. Create a project
            2. Convert the project into a project template
            3. Undo the project
            4. Check project documents
        """
        client_action = self.project_pigs.action_create_template_from_project()
        self.env['project.project'].browse(client_action['params']['project_id']).unlink()
        self.project_pigs.create_template_from_project_undo_callback(
            client_action['params']['callback_data']['args'][1]
        )
        self.project_pigs.action_create_template_from_project()

    def test_project_company_propagates_to_workspace(self):
        """
        Workspace is created without a company when a project has no company at creation
        (e.g. kanban quick-create). Setting the company afterwards must propagate to the workspace.
        """
        project = self.env['project.project'].create({
            'name': 'Kanban Project',
            'company_id': False,
        })
        workspace = project.documents_folder_id
        self.assertFalse(workspace.company_id)

        project.write({'company_id': self.env.company.id})

        self.assertEqual(
            workspace.company_id, self.env.company,
            "Workspace should receive the project company when it is the only linked project.",
        )

    def test_project_folder_access_on_followers_change(self):
        """
        Ensures that subscribing a partner grants 'edit' access to the project's
        document folder, and unsubscribing removes that access.
        """
        project = self.env["project.project"].create({"name": "Test Project"})
        partner = self.pro_admin.partner_id
        folder = project.documents_folder_id

        for visibility in ["invited_users", "followers"]:
            project.privacy_visibility = visibility

            # Subscribe: should grant edit access
            project.message_subscribe(partner_ids=partner.ids)
            access = folder.access_ids.filtered(lambda a: a.partner_id == partner)
            self.assertTrue(access, "Access record should be created when subscribing a partner")
            self.assertEqual(access.role, "edit", "Subscribed partner should have 'edit' access")

            # Unsubscribe: should remove access
            project.message_unsubscribe(partner_ids=partner.ids)
            access = folder.access_ids.filtered(lambda a: a.partner_id == partner)
            self.assertFalse(
                access,
                "Access record should be removed when unsubscribing a partner",
            )
