from odoo import fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    attendance_based = fields.Boolean(groups="base.group_system,hr.group_hr_manager,hr_payroll.group_hr_payroll_user")
