from odoo import models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def get_documents_operation_add_destination(self):
        self.ensure_one()

        if self.res_model == 'sign.request' and self.res_id and self.env['sign.request'].has_access('read'):
            sign_request = self.env['sign.request'].browse(self.res_id).exists()

            if sign_request and (ref_doc := sign_request.reference_doc) and ref_doc._name in ('project.task', 'project.project'):
                project = ref_doc if ref_doc._name == 'project.project' else ref_doc.project_id

                if project and project.documents_folder_id:
                    return {
                        'destination': str(project.documents_folder_id.id),
                        'display_name': project.documents_folder_id.display_name,
                    }

        return super().get_documents_operation_add_destination()
