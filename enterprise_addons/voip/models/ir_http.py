from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        res["groups"]["voip.group_voip_officer"] = self.env.user.has_group("voip.group_voip_officer")
        if user_companies := res.get("user_companies"):
            companies = self.env["res.company"].sudo().browse(
                list(user_companies["allowed_companies"]),
            )
            for company in companies:
                user_companies["allowed_companies"][company.id]["country_id"] = company.country_id.id
        return res
