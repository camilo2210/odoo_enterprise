# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = 'res.company'

    documents_bridge_settings = fields.Boolean()
    documents_bridge_folder_id = fields.Many2one(
        'documents.document', string='Test Mixin Folder', compute='_compute_documents_bridge_folder_id',
        store=True, readonly=False,
        domain=Domain('type', '=', 'folder') & Domain('shortcut_document_id', '=', False), check_company=True,
    )
    documents_bridge_folder_settings = fields.Boolean(default=True)
    documents_bridge_folder_folder_id = fields.Many2one(
        'documents.document', string='Test Mixin Folder Folder', compute='_compute_documents_bridge_folder_folder_id',
        store=True, readonly=False,
        domain=Domain('type', '=', 'folder') & Domain('shortcut_document_id', '=', False), check_company=True,
    )
    documents_bridge_tag_ids = fields.Many2many('documents.tag', 'res_company_documents_bridge_tags')

    @api.depends('documents_bridge_settings')
    def _compute_documents_bridge_folder_id(self):
        folder_id = self.env.ref('test_documents_full.documents_bridge_folder', raise_if_not_found=False)
        self._reset_default_documents_folder_id('documents_bridge_settings', 'documents_bridge_folder_id', folder_id)

    @api.depends('documents_bridge_folder_settings')
    def _compute_documents_bridge_folder_folder_id(self):
        folder_id = self.env.ref('test_documents_full.documents_bridge_folder_folder', raise_if_not_found=False)
        self._reset_default_documents_folder_id('documents_bridge_folder_settings', 'documents_bridge_folder_folder_id', folder_id)

    def _get_used_folder_ids_domain(self, folder_ids):
        return super()._get_used_folder_ids_domain(folder_ids) | (
            Domain('documents_bridge_folder_id', 'in', folder_ids)
            & Domain('documents_bridge_settings', '=', True)
        ) | (
            Domain('documents_bridge_folder_folder_id', 'in', folder_ids)
            & Domain('documents_bridge_folder_settings', '=', True)
        )
