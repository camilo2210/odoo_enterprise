# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import ValidationError


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    def _raise_if_used_folder(self):
        if folder_ids := self.filtered(lambda d: d.type == 'folder').ids:
            if self.env['hr.employee'].sudo().search_count(
                    [('hr_employee_payroll_folder_id', 'child_of', folder_ids)], limit=1):
                raise ValidationError(self.env._('Impossible to delete an employee "Payroll" folder'))
        return super()._raise_if_used_folder()
