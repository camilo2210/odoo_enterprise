# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Domain

from odoo.addons.mail.controllers.discuss.messaging_menu import DiscussMessagingMenuController


class AIMessagingMenuController(DiscussMessagingMenuController):
    def _get_ai_agent_channels_domain(self, agent_id):
        # sudo - discuss.channel: getting channels linked to this specific agent.
        # `ai_agent_id` is a `NO_ACCESS` field. Use sudo to get related channels, but
        # channel ACL and record rules still apply afterwards: this only resolves ids, the
        # caller runs the real, permission checked search on them.
        channel_ids = self.env["discuss.channel"].sudo()._search(
            Domain("ai_agent_id", "=", agent_id)
        )
        return Domain("id", "in", channel_ids)

    def _get_menu_tab_domain(self, tab_id):
        if not tab_id.startswith("ai-chat"):
            return super()._get_menu_tab_domain(tab_id)
        domain = Domain("channel_type", "=", "ai_chat")
        if ":" in tab_id:
            domain &= self._get_ai_agent_channels_domain(int(tab_id.split(":")[1]))
        return domain

    def _get_menu_tab_filter_domain(self, tab_id, filter_id):
        if tab_id.startswith("ai-chat") and filter_id == "ai_chat_unread":
            return Domain("self_member_id.is_unread", "=", True)
        if tab_id == "ai-chat" and filter_id.startswith("ai_agent:"):
            agent_id = int(filter_id.split(":")[1])
            return self._get_ai_agent_channels_domain(agent_id)
        return super()._get_menu_tab_filter_domain(tab_id, filter_id)
