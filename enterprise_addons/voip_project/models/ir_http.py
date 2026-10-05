from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        res["groups"]["project.group_project_user"] = self.env.user.has_group("project.group_project_user")
        return res
