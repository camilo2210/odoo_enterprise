# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.addons.mail.tools.discuss import Store


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    from_ai_automation = fields.Boolean(
        "From AI Automation",
        help="Channel opened by an automation rule or scheduled action.",
    )

    def _store_ai_fields(self, res: Store.FieldList):
        super()._store_ai_fields(res)
        res.attr("from_ai_automation", predicate=lambda c: c.channel_type == "ai_chat")

    def open_chat_window_action(self):
        self.ensure_one()
        self.check_access('read')
        if self.from_ai_automation and not self.is_member:
            # `ai_chat` channels are readable by their members only, and a run
            # starts with the agent as sole member
            self.sudo()._add_members(users=self.env.user)
        return super().open_chat_window_action()
