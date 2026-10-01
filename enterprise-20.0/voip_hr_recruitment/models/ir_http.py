from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        res["groups"]["hr_recruitment.group_hr_recruitment_interviewer"] = self.env.user.has_group("hr_recruitment.group_hr_recruitment_interviewer")
        return res
