# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tools import SQL


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'documents.mixin']
    _documents_record_folder_field_name = 'hr_employee_folder_id'

    document_count = fields.Integer(compute='_compute_document_count', groups="hr.group_hr_user")
    hr_employee_folder_id = fields.Many2one(
        'documents.document', string="HR Employee Folder", copy=False, groups="base.group_system,hr.group_hr_user",
        domain="['|', '&', ('res_model', '=', 'hr.employee'), ('res_id', '=', id), ('res_model', '=', False)]")

    def _get_document_folder(self):
        return self.hr_employee_folder_id

    def _compute_document_count(self):
        """Count the documents that will be found when opening action_open_documents."""
        self.document_count = 0
        employees = self.filtered('id')  # documents are only linked to stored employees
        if not employees:
            return
        for employee, count in employees._get_document_counts().items():
            employee.document_count = count

    def _get_document_counts(self):
        if not self:
            return {}
        linked_records = SQL(', ').join(
            SQL('(%s, %s, %s)', employee.id, res_model, res_id)
            for employee, ids_per_model in self._get_linked_records().items()
            for res_model, res_ids in ids_per_model.items()
            for res_id in res_ids
        )
        linked_query = self.env['documents.document']._search(
            self._get_documents_domain() & Domain('shortcut_document_id', '=', False))
        folders_query = self.env['documents.document']._search([('type', '=', 'folder')])
        documents_query = self.env['documents.document']._search(
            Domain('type', '!=', 'folder') & Domain('shortcut_document_id', '=', False))
        self.flush_model(['hr_employee_folder_id'])
        self.env['documents.document'].flush_model(['active', 'folder_id', 'res_model', 'res_id'])
        query = SQL(
            """
            -- Recursion to avoid less efficient parent_path use.
            WITH RECURSIVE accessible_folder AS (%(folders)s),
            -- The folder of each employee and, recursively, its subfolders, interrupting for
            -- access rights (unless sudo): an inaccessible folder hides its content.
            employee_folder (employee_id, folder_id) AS (
                SELECT employee.id, root.id
                  FROM hr_employee AS employee
                  JOIN accessible_folder AS root
                    ON root.id = employee.hr_employee_folder_id
                 WHERE employee.id = ANY(%(employee_ids)s)
                 UNION ALL
                SELECT parent.employee_id, subfolder.id
                  FROM employee_folder AS parent
                  JOIN accessible_folder AS subfolder
                    ON subfolder.folder_id = parent.folder_id
            ),
            linked_record (employee_id, res_model, res_id) AS (VALUES %(linked_records)s),
            employee_document AS (
                SELECT linked_record.employee_id, document.id
                  FROM (%(linked_documents)s) AS document
                  JOIN linked_record
                    ON linked_record.res_model = document.res_model
                   AND linked_record.res_id = document.res_id
                 UNION -- deduplicates docs in employee folder and those linked to one of their records
                SELECT employee_folder.employee_id, document.id
                  FROM (%(documents)s) AS document
                  JOIN employee_folder
                    ON employee_folder.folder_id = document.folder_id
            )
            SELECT employee_id, COUNT(*)
              FROM employee_document
          GROUP BY employee_id
        """,
            employee_ids=self.ids,
            linked_records=linked_records,
            folders=folders_query.select(*(folders_query.table[f] for f in ('id', 'folder_id'))),
            linked_documents=linked_query.select(*(linked_query.table[f] for f in ('id', 'res_model', 'res_id'))),
            documents=documents_query.select(*(documents_query.table[f] for f in ('id', 'folder_id'))),
        )
        counts = dict(self.env.execute_query(query))
        return {employee: counts.get(employee.id, 0) for employee in self}

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        if not self.env.context.get('salary_simulation', False):
            employees._generate_employee_documents_folders()
        return employees

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals and len(self) == 1:
            # This makes no sense to rename multiple employees with the same name. This would probably be an error.
            # So we rename the folder only if one employee is renamed at a time.
            self.sudo().hr_employee_folder_id.write({'name': vals['name']})
        return result

    def _get_documents_domain(self):
        all_ids_per_model = defaultdict(list)
        for employee, employee_ids_per_model in self._get_linked_records().items():
            for res_model, res_ids in employee_ids_per_model.items():
                all_ids_per_model[res_model] += res_ids
        return Domain('type', '!=', 'folder') & Domain.OR(
            Domain('res_model', '=', res_model) & Domain('res_id', 'in', res_ids)
            for res_model, res_ids in all_ids_per_model.items()
        )

    def _get_linked_records(self):
        """Return a map of record ids of each employee whose documents are theirs: {res_model: res_ids}."""
        return {
            employee: {
                'hr.employee': employee.ids,
                'hr.version': employee.with_context(active_test=False).sudo().version_ids.ids,
            } for employee in self
        }

    def action_open_documents(self):
        """ Open and display all the content of the employee subfolder under HR > Employee. """
        self.ensure_one()
        is_hr = self.env.user.has_groups('hr.group_hr_user')
        if not is_hr and self.env.user.employee_id != self:
            raise AccessError(_('You cannot access the employee\'s folder.'))
        if is_hr and not self.hr_employee_folder_id:
            self._generate_employee_documents_folders()

        action = super().action_open_documents()
        action['domain'] = self._get_documents_domain()  # replace until we decide if we replicate this logic for all
        if (folder := self.sudo().hr_employee_folder_id.sudo(self.env.su)) and folder.user_permission != 'none':
            # Sync with document_count; Without this access, children documents appear in "Shared With Me".
            action['domain'] |= Domain('folder_id', 'child_of', folder.id)
        # Sync with document_count, useful for created payslips, but easier to have in documents_hr.
        action['context'] |= {'search_default_no_shortcuts': True}
        return action

    def _generate_employee_documents_folders(self, skip_subfolders=False):
        """ Employee document folder is meant to be used by HR only to store all the documents they need regarding the
         employee (E.g.: ID Card, Drive License, etc..). The employee does not have access to this folder,
         nor the documents inside it (by default at least) """
        employees_without_folder = self.filtered(lambda e: not e.hr_employee_folder_id and e.company_id.active)
        employees_without_folder.company_id._generate_missing_documents_hr_groups()
        folders = self.env["documents.document"].sudo().create([{
            'name': employee.name,
            'type': 'folder',
            'folder_id': employee.company_id.documents_employee_folder_id.id,
            'company_id': employee.company_id.id,
            'access_internal': 'none',
            'access_via_link': 'none',
            'is_access_via_link_hidden': True,
            'owner_id': False,
            'access_ids': [
                Command.create({'group_id': group.id, 'role': 'edit'})
                for group in employee.company_id._get_documents_employee_folders_editor_groups()
            ],
        } for employee in employees_without_folder]).sudo(self.env.su)
        for employee, folder in zip(employees_without_folder, folders):
            employee.hr_employee_folder_id = folder.id

        if not skip_subfolders:
            self.filtered(lambda e: e.company_id.active)._generate_employee_documents_subfolders()

    def _get_reserved_employee_subfolders(self):
        """ Subfolders of the employee folders generated by a module, not by the company setting.

        They are neither created nor deleted by `_generate_employee_documents_subfolders`.
        """
        return self.env['documents.document']

    def _generate_employee_documents_subfolders(self):
        """ Generate subfolders under the employee folder, following what is specified on the company
         -> res_config_settings.employee_subfolders
         Removing a folder name from the setting should not delete the folder if it's not empty.
         Existing folders should not be recreated.
         Only newly added folder name should generate a new subfolder.
         """
        Documents = self.env['documents.document']
        create_subfolders_vals = []
        subfolders_to_delete = Documents

        subfolders = Documents.search([
            ('type', '=', 'folder'),
            ('folder_id', 'in', self.hr_employee_folder_id.ids),
            ('id', 'not in', self.sudo()._get_reserved_employee_subfolders().ids)])
        subfolders_by_employee_folder = subfolders.grouped('folder_id')
        for company in self.company_id:
            subfolder_names = [
                name for name in company.employee_subfolders.split(',') if name
            ] if company.employee_subfolders else []
            company_employees = self.filtered(lambda e: e.company_id == company and e.hr_employee_folder_id)
            for employee in company_employees:
                # Add new folders added to the list
                existing_subfolders = subfolders_by_employee_folder.get(employee.hr_employee_folder_id, Documents)
                added_subfolder_names = list(set(subfolder_names) - set(existing_subfolders.mapped('name')))
                for subfolder_name in added_subfolder_names:
                    create_subfolders_vals.append({
                        'name': subfolder_name.strip(),
                        'type': 'folder',
                        'folder_id': employee.hr_employee_folder_id.id,
                        'company_id': company.id,
                        'owner_id': False,
                    })

                # Delete removed folder from the list.
                # -> Side effect : folders created manually that are still empty will be deleted.
                removed_subfolders_names = list(set(existing_subfolders.mapped('name')) - set(subfolder_names))
                subfolders_to_delete |= existing_subfolders.filtered(
                    lambda f: f.name in removed_subfolders_names and not f.children_ids)
        if create_subfolders_vals:
            self.env["documents.document"].sudo().create(create_subfolders_vals)
        subfolders_to_delete.unlink()
