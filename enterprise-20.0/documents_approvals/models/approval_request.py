# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ApprovalRequest(models.Model):
    _name = 'approval.request'
    _inherit = ['approval.request', 'documents.mixin']

    documents_enabled = fields.Boolean(related='company_id.documents_approvals_settings')

    def _get_document_vals_access_rights(self):
        """Make sure (only) request owner and approval users can view the document."""
        return {
            'access_via_link': 'view',
            'access_internal': 'none',
            'is_access_via_link_hidden': False,
        }

    def _get_document_owner(self):
        return self.env.user

    def _get_document_members(self):
        return [(self.request_owner_id.partner_id, ('view', False))]

    def _get_document_tags(self):
        return self.company_id.approvals_tag_ids

    def _get_document_folder(self):
        return self.company_id.approvals_folder_id

    def _get_document_partner(self):
        return self.partner_id

    def _check_create_documents(self):
        return self.company_id.documents_approvals_settings and super()._check_create_documents()

    def action_get_attachment_view(self):
        if not self.company_id.documents_approvals_settings:
            return super().action_get_attachment_view()
        return super().action_open_documents()
