# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def get_frontend_session_info(self):
        session_info = super().get_frontend_session_info()
        website = self.env.website
        session_info.update({"website_tz": website.tz})
        return session_info
