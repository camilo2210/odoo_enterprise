from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    zkteco_emp_id = fields.Char(groups="hr.group_hr_user")

    _unique_zk_emp_id_company = models.Constraint(
        "UNIQUE(zkteco_emp_id, company_id)",
        "ZKTeco Employee ID must be unique per company.",
    )
