from odoo import fields, models


class SignTemplate(models.Model):
    _name = 'sign.template'
    _inherit = ['sign.template']

    def _default_folder_id(self):
        return self.env.ref('documents_sign.document_sign_folder', raise_if_not_found=False)

    folder_id = fields.Many2one('documents.document', 'Signed Document Folder',
                                default=_default_folder_id,
                                domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False)]")
    documents_tag_ids = fields.Many2many('documents.tag', string="Signed Document Tags")
