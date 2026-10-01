from odoo import models


class AccountDocumentImportMixin(models.AbstractModel):
    _inherit = 'account.document.import.mixin'

    def _fix_attachments_on_record_from_files_data(self, valid_files_data, extra_files_data):
        super()._fix_attachments_on_record_from_files_data(valid_files_data, extra_files_data)
        valid_attachments = self._from_files_data(valid_files_data)
        valid_attachments._account_update_or_create_documents(self)
