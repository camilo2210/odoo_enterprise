# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    document_count = fields.Integer(string='Documents', compute='_compute_document_count')

    @api.depends_context('uid')
    def _compute_document_count(self):
        self.document_count = 0
        if user_employees := self.filtered('is_user'):  # support duplicates
            employees_counts = user_employees.employee_id._get_document_counts()
            for user_employee in user_employees:
                user_employee.document_count = employees_counts[user_employee.employee_id]

    def action_see_documents(self):
        self.ensure_one()
        if self.is_user:
            return self.employee_id.action_open_documents()
