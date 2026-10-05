from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import _


class ProjectProject(models.Model):
    _name = 'project.project'
    _inherit = ['project.project', 'documents.mixin']
    _documents_record_folder_field_name = 'documents_folder_id'

    documents_folder_id = fields.Many2one(
        'documents.document', string="Documents Folder", copy=False, context=lambda env: {
            'default_folder_id': env.company.documents_project_folder_id.id,
        },
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False), "
               "'|', ('company_id', '=', False), ('company_id', '=', company_id),"
               "'|', '&', ('res_model', '=', 'project.project'), ('res_id', '=', id), ('res_model', '=', False)]",
        index='btree_not_null',
        help="Folder in which all of the documents of this project will be categorized.")
    document_count = fields.Integer(compute='_compute_document_count', export_string_translation=False)
    document_ids = fields.One2many('documents.document', compute='_compute_document_count', export_string_translation=False)
    documents_folder_user_permission = fields.Selection(related='documents_folder_id.user_permission', export_string_translation=False)

    @api.ondelete(at_uninstall=False)
    def _archive_folder_on_projects_unlinked(self):
        """ Archives the project folder if all its related projects are unlinked. """
        folders_sudo = self.sudo().documents_folder_id
        # include archived projects: they still reference their folder
        remaining_projects_sudo = self.env['project.project'].sudo().with_context(active_test=False).search([
            ('documents_folder_id', 'in', folders_sudo.ids),
            ('id', 'not in', self.ids),
        ])
        orphan_folders_sudo = folders_sudo - remaining_projects_sudo.documents_folder_id
        orphan_folders_sudo.sudo(False)._filtered_access('unlink').action_archive()

    @api.constrains('documents_folder_id')
    def _check_company_is_folders_company(self):
        for project in self.filtered('documents_folder_id'):
            if folder := project['documents_folder_id']:
                if folder.company_id and project.company_id != folder.company_id:
                    raise UserError(_(
                        'The "%(folder)s" folder should either be in the "%(company)s" company like this'
                        ' project or be open to all companies.',
                        folder=folder.name, company=project.company_id.name)
                    )

    def _compute_document_count(self):
        docs_by_record = self.env['documents.document']._read_group(
            self._get_documents_domain(),
            groupby=['res_model', 'res_id'],
            aggregates=['id:recordset'],
        )
        docs_by_record = {(res_model, res_id): doc for res_model, res_id, doc in docs_by_record}
        for project in self:
            document_ids = docs_by_record.get(('project.project', project.id), self.env['documents.document'])
            for task in project.task_ids:
                document_ids |= docs_by_record.get(('project.task', task.id), self.env['documents.document'])
            project.document_ids = document_ids
            project.document_count = len(document_ids)

    def _create_missing_folders(self):
        folders_to_create_vals = []
        projects_with_folder_to_create = []
        documents_project_folder_id = self.env.company.documents_project_folder_id.id

        for project in self:
            if not project.documents_folder_id:
                folder_vals = {
                    'access_internal': 'edit' if project.privacy_visibility in ['employees', 'portal'] else 'none',
                    'company_id': project.company_id.id,
                    'folder_id': documents_project_folder_id,
                    'name': project.name,
                    'type': 'folder',
                }
                folders_to_create_vals.append(folder_vals)
                projects_with_folder_to_create.append(project)

        if folders_to_create_vals:
            created_folders = self.env['documents.document'].sudo().create(folders_to_create_vals)
            # Enable the embedded actions of the document's project folder to the newly created project folders
            project_folder_actions_dict = self.env['documents.document'].sudo()._get_folder_embedded_actions([documents_project_folder_id])
            for embedded_action in project_folder_actions_dict.get(documents_project_folder_id, []):
                for folder in created_folders:
                    folder.action_folder_embed_action(folder.id, embedded_action.action_id.id)
            for project, folder in zip(projects_with_folder_to_create, created_folders):
                project.sudo().documents_folder_id = folder

    def _get_document_folder(self):
        return self.documents_folder_id

    def _get_document_vals_access_rights(self):
        return {}

    def _get_documents_domain(self):
        return super()._get_documents_domain() | Domain(
            [('type', '!=', 'folder'), ('res_model', '=', 'project.task'), ('res_id', 'in', self.task_ids.ids)]
        )

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        if not self.env.context.get('no_create_folder'):
            projects._create_missing_folders()
        return projects

    def write(self, vals):
        if 'company_id' in vals:
            for project in self:
                if project.documents_folder_id and project.documents_folder_id.company_id and len(project.documents_folder_id.project_ids) > 1:
                    other_projects = project.documents_folder_id.project_ids - self
                    if other_projects and other_projects.company_id.id != vals['company_id']:
                        lines = [f"- {project.name}" for project in other_projects]
                        raise UserError(_(
                            'You cannot change the company of this project, because its folder is linked to the other following projects that are still in the "%(other_company)s" company:\n%(other_folders)s\n\n'
                            'Please update the company of all projects so that they remain in the same company as their folder, or leave the company of the "%(folder)s" folder blank.',
                            other_company=other_projects.company_id.name, other_folders='\n'.join(lines), folder=project.documents_folder_id.name))

        if 'name' in vals:
            projects = self.filtered(
                lambda p: (
                    (folder := p.documents_folder_id.sudo())
                    and len(folder.project_ids) == 1
                    and p.name == folder.name
                )
            )
            projects.documents_folder_id.sudo().name = vals['name']

        project_root_documents = self.env['documents.document']
        if 'documents_folder_id' in vals:
            project_root_documents = self.documents_folder_id.children_ids

        res = super().write(vals)
        if 'company_id' in vals:
            for project in self:
                if not (folder := project.documents_folder_id):
                    continue

                linked_projects = folder.project_ids
                linked_companies = linked_projects.company_id

                if not linked_companies:
                    folder.company_id = False
                elif len(linked_companies) == 1 and all(p.company_id for p in linked_projects):
                    folder.company_id = linked_companies
        if not self.env.context.get('no_create_folder'):
            self._create_missing_folders()
        if project_root_documents:
            project_root_documents.folder_id = self.documents_folder_id

        return res

    def _change_privacy_visibility(self, new_visibility):
        """ Override to Add/remove access rights of the internal followers of the project
            to the documents folder and its documents based on the new privacy visibility. """
        super()._change_privacy_visibility(new_visibility)
        for project in self.filtered(lambda p: p.privacy_visibility != new_visibility):
            project_documents = project.documents_folder_id | project.document_ids
            internal_partners = project.message_partner_ids.filtered(lambda p: not p.partner_share)
            access_internal = 'edit' if new_visibility in ('employees', 'portal') else 'none'
            new_permission = False if new_visibility in ('employees', 'portal') else 'edit'

            project_documents.sudo().action_update_access_rights(
                access_internal=access_internal,
                partners=dict.fromkeys(internal_partners, (new_permission, False))
            )

    def copy(self, default=None):
        # We have to add no_create_folder=True to the context, otherwise a folder
        # will be automatically created during the call to create.
        copied_projects = super(ProjectProject, self.with_context(no_create_folder=True)).copy(default).with_env(self.env)

        for old_project, new_project in zip(self, copied_projects):
            if not self.env.context.get('no_create_folder') and old_project.documents_folder_id:
                new_project.documents_folder_id = old_project.documents_folder_id.sudo().copy(
                        {'name': new_project.name, 'owner_id': False}
                    )

        new_documents_sudo = self.env['documents.document'].sudo().search([
            ('type', '!=', 'folder'), ('id', 'child_of', copied_projects.documents_folder_id.ids)
        ])
        for new_project in copied_projects:
            new_documents_sudo.filtered_domain([('id', 'child_of', new_project.documents_folder_id.ids)]).write({
                'res_model': 'project.project',
                'res_id': new_project.id,
            })
        return copied_projects

    def create_template_from_project_undo_callback(self, callbacks):
        super().create_template_from_project_undo_callback(callbacks)
        if self.documents_folder_id and callbacks.get("unarchive_project"):
            self.documents_folder_id.action_unarchive()

    def _get_template_from_project_undo_callbacks(self):
        callbacks = super()._get_template_from_project_undo_callbacks()
        if self.documents_folder_id and callbacks.get("unarchive_project"):
            self.documents_folder_id.action_archive()
        return callbacks

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        res = super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)
        if (
            self.privacy_visibility in ['invited_users', 'followers']
            and partner_ids
        ):
            internal_partners = self.env['res.partner'].search([
                ('id', 'in', partner_ids),
                ('user_ids.share', '=', False),
            ]).ids
            self.documents_folder_id.action_update_access_rights(
                partners={
                    partner: ('edit', False) for partner in internal_partners
                },
            )
        return res

    def message_unsubscribe(self, partner_ids=None):
        if (
            self.privacy_visibility in ['invited_users', 'followers']
            and partner_ids
        ):
            self.documents_folder_id.action_update_access_rights(
                partners={
                    partner: (False, False) for partner in partner_ids
                },
            )
        super().message_unsubscribe(partner_ids=partner_ids)

    def _get_document_partner(self):
        return self.partner_id
