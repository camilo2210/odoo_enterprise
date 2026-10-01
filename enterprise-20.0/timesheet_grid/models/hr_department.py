from odoo import models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    def write(self, vals):
        result = super().write(vals)
        if "company_id" in vals:
            # sudo: the private rules of the other users have to be cleaned up too
            self.env["aw.rule"].sudo().search([
                ("applies_to", "=", "departments"),
                ("department_ids", "child_of", self.ids),
                ("company_id", "!=", False),
            ])._remove_records_from_other_companies()
        return result
