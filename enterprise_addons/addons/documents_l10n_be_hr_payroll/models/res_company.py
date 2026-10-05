# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _create_payroll_managers_document(self, data, filename):
        """Synchronize the company-wide payroll report in Documents, shared with the payroll managers only."""
        self.ensure_one()
        document = self.env['documents.document'].create({
            'owner_id': False,
            'raw': data,
            'name': filename,
            'folder_id': self.documents_employee_folder_id.id,
            'access_internal': 'none',
            'access_via_link': 'none',
            'is_access_via_link_hidden': True,
            'access_ids': False,  # do not inherit access from the parent
        })
        self.env['documents.access'].sudo().create([
            {'document_id': document.id, 'partner_id': user.partner_id.id, 'role': 'edit'}
            for user in self._get_company_group_users(self.env.ref('hr_payroll.group_hr_payroll_manager'))
        ])
