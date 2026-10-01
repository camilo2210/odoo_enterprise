from odoo import models


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'documents.mixin']

    def _check_create_documents(self):
        return self.project_id and super()._check_create_documents()

    def _get_document_folder(self):
        return self.project_id.documents_folder_id

    def _get_document_vals_access_rights(self):
        if folder := self._get_document_folder():
            return {
                'access_via_link': folder.access_via_link,
                'access_internal': folder.access_internal,
                'is_access_via_link_hidden': folder.is_access_via_link_hidden,
            }
        return super()._get_document_vals_access_rights()
