from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        if not res["can_insert_in_spreadsheet"]:
            res["can_insert_in_spreadsheet"] = self.env.user.has_group(
                "account.group_account_user"
            )
        return res
