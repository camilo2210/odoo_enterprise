from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_linked_records(self):
        all_linked_records = super()._get_linked_records()
        for employee, employee_linked_records in all_linked_records.items():
            employee_linked_records['hr.leave'] = employee.sudo().leave_ids.ids
        return all_linked_records
