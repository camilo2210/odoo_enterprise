from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_document_attachments_to_sync(self):
        if self.expense_ids:
            expense_atts_checksums = self.expense_ids.message_main_attachment_id.mapped('checksum')
            return self.attachment_ids.filtered(lambda att: att.checksum in expense_atts_checksums)
        return super()._get_document_attachments_to_sync()
