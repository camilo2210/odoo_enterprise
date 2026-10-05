# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SignRequest(models.Model):
    _inherit = 'sign.request'

    def _check_create_documents(self):
        """Prevent the creating a document in the Sign folder, since the HR flow
        creates the signed document in the employee's folder (from SignContract.sign()).
        """
        if not super()._check_create_documents():
            return False

        employee = self.env['hr.employee'].with_context(active_test=False).search([('sign_request_ids', 'in', self.ids)], limit=1)
        if employee and employee._check_create_documents():
            return False

        version = self.env['hr.version'].with_context(active_test=False).search([('sign_request_ids', 'in', self.ids)], limit=1)
        return not (version and version._check_create_documents())
