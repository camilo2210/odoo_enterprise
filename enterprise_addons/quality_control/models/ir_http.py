# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        if not res["can_insert_in_spreadsheet"]:
            res["can_insert_in_spreadsheet"] = self.env.user.has_group(
                "quality.group_quality_manager"
            ) and bool(self.env["quality.spreadsheet.template"].search_count([], limit=1))
        return res
