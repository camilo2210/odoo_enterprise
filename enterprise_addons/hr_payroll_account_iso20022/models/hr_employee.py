# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_invalid_iban_employee_ids(self, employees_data=False):
        if not employees_data:
            employees_data = self._get_account_holder_employees_data()
        return list({employee['id'] for employee in employees_data if not self.env['res.partner.bank']._is_iban_valid(employee['account_number'])})
