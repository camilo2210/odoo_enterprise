from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_based = fields.Boolean(groups="base.group_system,hr.group_hr_manager,hr_payroll.group_hr_payroll_user")
