# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.mail.tools.discuss import Store


class ResUsers(models.Model):
    _inherit = "res.users"

    def _store_init_global_fields(self, res: Store.FieldList):
        super()._store_init_global_fields(res)
        domain = [
            ("use_website_helpdesk_livechat", "=", True),
            ("company_id", "in", self.env.context.get("allowed_company_ids", [])),
        ]
        res.attr(
            "helpdesk_livechat_active",
            self.env["helpdesk.team"].sudo().search_count(domain, limit=1) > 0,
        )
        res.attr("has_access_create_ticket", self.has_group("helpdesk.group_helpdesk_user"))
