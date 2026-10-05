from odoo import _, models, fields
from odoo.exceptions import UserError


class SignImportFromDocuments(models.TransientModel):
    _name = 'sign.import.documents'
    _description = 'Wizard to select PDF documents from the Documents app to sign'

    selected_document = fields.Many2one('documents.document', string='Selected Document', domain="[('mimetype', '=', 'application/pdf')]", required=True)

    def action_import_and_create(self):
        self.ensure_one()

        if not self.selected_document:
            raise UserError(_("No document selected to import and sign."))

        sign_folder = self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False)
        return self.selected_document.document_sign_create_sign_template(sign_folder and sign_folder.id)
