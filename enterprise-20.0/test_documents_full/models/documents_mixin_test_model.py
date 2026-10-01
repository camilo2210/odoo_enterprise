# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class DocumentsMixinTestModel(models.Model):
    _name = 'documents.mixin.test.model'
    _description = 'Documents Mixin Test Model'
    _inherit = ['documents.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company')
    document_count = fields.Integer(compute='_compute_document_count', string='Documents')

    def _check_create_documents(self):
        self.ensure_one()
        return self.company_id.documents_bridge_settings and super()._check_create_documents()

    def _get_document_owner(self):
        return self.env.user

    def _get_document_folder(self):
        return self.company_id.documents_bridge_folder_id

    def _get_document_tags(self):
        return self.company_id.documents_bridge_tag_ids

    def _get_document_vals_access_rights(self):
        return {}  # Inherit from folder

    def _compute_document_count(self):
        document_data = self.env["documents.document"]._read_group(
            [("res_id", "in", self.ids), ("res_model", "=", self._name)], groupby=["res_id"], aggregates=["__count"]
        )
        mapped_data = dict(document_data)
        for record in self:
            record.document_count = mapped_data.get(record.id, 0)


class DocumentsMixinTestModelFolder(models.Model):
    _name = 'documents.mixin.folder.test.model'
    _description = 'Documents Mixin Folder Test Model'
    _inherit = ['documents.mixin', 'mail.thread']

    name = fields.Char(string='Name')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company')

    def _check_create_documents(self):
        return self.company_id.documents_bridge_folder_settings and super()._check_create_documents()

    def _get_document_folder(self):
        return self.company_id.documents_bridge_folder_folder_id

    def _get_document_vals(self, attachment):
        """Create a folder from an uploaded attachment to test alias creation with correct values."""
        return super()._get_document_vals(attachment) | {
            'alias_name': attachment.name,  # necessary to create the alias with `mail.alias.mixin.optional`
            'attachment_id': None,
            'name': attachment.name,
            'type': 'folder',
        }


class DocumentsMixinTestFolderPerInstance(models.Model):
    _name = 'documents.mixin.test.folder.per.instance'
    _description = 'Documents Mixin Test Folder Per Instance'
    _inherit = ['documents.mixin', 'mail.thread']
    _documents_record_folder_field_name = 'record_folder_id'

    name = fields.Char(string="Name")
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda self: self.env.company)
    record_folder_id = fields.Many2one(
        'documents.document', string='Linked Folder', copy=False,
        domain=Domain('type', '=', 'folder') & Domain('shortcut_document_id', '=', False),
        check_company=True,
    )
    # Used to test that the documents.mixin values are applied post-creation
    document_owner_id = fields.Many2one('res.users', string='Document Owner')
    document_partner_id = fields.Many2one('res.partner', string='Document Contact')
    document_tag_ids = fields.Many2many('documents.tag', string='Document Tags')
    document_member_ids = fields.Many2many('res.partner', string='Document Members')

    def _get_document_folder(self):
        return self.record_folder_id if self.company_id.documents_bridge_settings else self.env['documents.document']

    def _get_document_owner(self):
        return self.document_owner_id

    def _get_document_partner(self):
        return self.document_partner_id

    def _get_document_tags(self):
        return self.document_tag_ids

    def _get_document_members(self):
        return [(partner, ('view', False)) for partner in self.document_member_ids]
