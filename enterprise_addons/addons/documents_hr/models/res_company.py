# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = "res.company"

    documents_employee_folder_id = fields.Many2one('documents.document', string="Employees Folder",
        domain=[('type', '=', 'folder'), ('shortcut_document_id', '=', False)], check_company=True,
        required=True)
    employee_subfolders = fields.Char(
        "Employees Subfolder",
        help='Comma separated list of folder names that need to be created under each employee folder.')
    documents_hr_contracts_tags = fields.Many2many('documents.tag', 'documents_hr_contracts_tags_table')
    documents_hr_group_id = fields.Many2one(
        'res.group.functional', string="HR Documents Default Group",
        help="Group given editor access on the employees folders created from now on. "
             "Changing it does not affect the existing folders.")

    def init(self):
        """Create required documents_employee_folder_id at the first install."""
        super().init()
        if unconfigured_companies := self.env['res.company'].with_context(active_test=False).search(
                [('documents_employee_folder_id', '=', False)]):
            unconfigured_companies._init_generate_employee_documents_main_folders()

    def _get_used_folder_ids_domain(self, folder_ids):
        return super()._get_used_folder_ids_domain(folder_ids) | Domain(
            'documents_employee_folder_id', 'in', folder_ids)

    @api.model_create_multi
    def create(self, vals_list):
        # The Employees folder is required: it must be created before the company, as `base` does for
        # the (also required) partner of the company. The company and the access rights of the folders
        # created here are set by `_generate_employee_documents_main_folders` below.
        if (
            "default_documents_employee_folder_id" not in self.env.context
            and (vals_without_folder := [vals for vals in vals_list if not vals.get('documents_employee_folder_id')])
        ):
            folders_sudo = self.env['documents.document'].sudo().create([
                self._get_documents_employee_folder_vals(vals.get('name'))
                for vals in vals_without_folder
            ])
            for vals, folder_sudo in zip(vals_without_folder, folders_sudo):
                vals['documents_employee_folder_id'] = folder_sudo.id
        companies = super().create(vals_list)
        companies._generate_employee_documents_main_folders()
        return companies

    def write(self, vals):
        """ Override to move all employee subfolders if the HR Employee folder has been modified in settings.
        And ensure that the employees that have no folder yet get one. """
        subfolders_changed = vals.get('employee_subfolders')
        employees_without_subfolder = self.env['hr.employee']
        if vals.get('documents_employee_folder_id'):
            employees = self.env['hr.employee'].sudo().search([('company_id', 'in', self.ids)])
            # Might be that some employees have no folder yet (e.g. archived when the module was
            # installed, or created for a salary simulation).
            employees_without_subfolder = employees.filtered(lambda e: not e.hr_employee_folder_id)
            employees_with_subfolders = employees - employees_without_subfolder
            employees_with_subfolders.hr_employee_folder_id.with_context(
                documents_move_skip_rights_sync=True
            ).folder_id = vals['documents_employee_folder_id']
            # done in two times otherwise the folder_id will propagate its own access rights instead of the right values
            employees_with_subfolders.hr_employee_folder_id.write({
                'access_via_link': 'none',
                'access_internal': 'none',
            })
        result = super().write(vals)
        if employees_without_subfolder:
            employees_without_subfolder._generate_employee_documents_folders(skip_subfolders=subfolders_changed)
        if subfolders_changed:
            self.env['hr.employee'].search([('company_id', 'in', self.ids)])._generate_employee_documents_subfolders()
        return result

    @api.model
    def _get_documents_employee_folder_vals(self, company_name):
        """ Values of the Employees folder of a company, whose id may not be known yet (see `create`)."""
        return {
            'name': self.env._('Employees - %s', company_name),
            'type': 'folder',
            'folder_id': False,
            'is_access_via_link_hidden': True,
            'owner_id': False,
        }

    def _generate_employee_documents_main_folders(self):
        """ Ensure that each company has its Employees folder, shared with its functional groups.

        Idempotent: the folder may have been created before the company (see `create`) or be fully set
        up already, as the extensions use this method to act on existing folders.
        """
        self._init_generate_employee_documents_main_folders()

    def _init_generate_employee_documents_main_folders(self):
        """Prevent overrides when executed in `init` where things can break."""
        self._generate_missing_documents_hr_groups()
        for company in self:
            folder_sudo = company.sudo().documents_employee_folder_id
            if not folder_sudo:
                folder_sudo = self.env['documents.document'].sudo().create(
                    self._get_documents_employee_folder_vals(company.name))
                company.sudo().documents_employee_folder_id = folder_sudo.id
            if not folder_sudo.company_id:
                folder_sudo.company_id = company.id
            editor_groups = company._get_documents_employee_folders_editor_groups()
            if missing_groups := editor_groups - folder_sudo.access_ids.group_id:
                folder_sudo.access_ids = [
                    Command.create({"group_id": group.id, "role": "edit"})
                    for group in missing_groups
                ]

    def _get_documents_employee_folders_editor_groups(self):
        """ Functional groups given editor access on the employee folders of the company."""
        self.ensure_one()
        return self.documents_hr_group_id

    def _generate_missing_documents_hr_groups(self):
        """Create and assign a group for HR users if it doesn't exist on active companies."""
        res_group_hr_user = self.env.ref("hr.group_hr_user")
        for company in self.filtered(lambda c: c.active and not c.documents_hr_group_id):
            company.sudo().documents_hr_group_id = self.env["res.group.functional"].sudo().create({
                'name': self.env._("HR (%(company_name)s)", company_name=company.name),
                'responsible_ids': [Command.link(company._get_documents_hr_group_responsible().id)],
                'user_ids': [Command.set(company._get_company_group_users(res_group_hr_user).ids)],
            })

    def _get_documents_hr_group_responsible(self):
        """ Responsible for the functional groups created for the employee folders."""
        return (
            self.env.user
            if self.env.user.has_group("base.group_erp_manager")
            else self.env.ref("base.user_root")
        )

    def _get_company_group_users(self, group):
        """ Users of the given group (implied groups included) allowed in this company. """
        self.ensure_one()
        return group.sudo().all_user_ids.filtered(lambda user: self in user.company_ids)
