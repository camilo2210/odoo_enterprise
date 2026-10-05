# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError


class DocumentsAccess(models.Model):
    _inherit = "documents.access"

    @api.constrains("document_id", "partner_id", "role")
    def _check_spreadsheet(self):
        for access in self:
            if access.document_id.handler == 'frozen_spreadsheet' and access.role == 'edit':
                raise ValidationError(_('Frozen Spreadsheets can not be editable.'))
