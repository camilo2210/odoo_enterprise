from odoo import api, models, fields
from odoo.fields import Domain


class AIAttachmentVacuum(models.Model):
    _name = "ai.attachment.vacuum"
    _description = "AI Generated Attachments that aren't used and should be autovacuumed"

    attachment_id = fields.Many2one(
        "ir.attachment", string="Attachment", required=True, ondelete="cascade"
    )

    def _create_attachments_and_mark_unused(self, vals_list):
        attachments = self.env['ir.attachment'].create(vals_list)
        self.create([{'attachment_id': att.id} for att in attachments])
        return attachments

    @api.model
    def mark_attachments_used(self, attachment_ids):
        if not attachment_ids:
            return
        attachments = self.env['ir.attachment'].browse(attachment_ids)
        attachments.check_access('write')
        attachments_vacuum = self.sudo().search([('attachment_id', 'in', attachments.ids)])
        attachments_vacuum.unlink()

    @api.autovacuum
    def _remove_unused_attachments(self):
        old_unused = Domain('create_date', '<', '-1d')
        linked = Domain('attachment_id.res_model', '!=', False) & Domain('attachment_id.res_id', '!=', False)

        # Unlinked attachments: delete the ir.attachment (cascades to vacuum record)
        self.search(old_unused & ~linked).mapped("attachment_id").unlink()
        # Linked attachments: just remove the vacuum record, keep the attachment
        self.search(old_unused & linked).unlink()
