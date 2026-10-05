# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Domain

from odoo.addons.ai.controllers.messaging_menu import AIMessagingMenuController


class AIAgenticMessagingMenuController(AIMessagingMenuController):
    def _get_menu_tab_domain(self, tab_id):
        # automation runs get their own tab, and leave the AI chat tab
        if tab_id.startswith("ai-chat"):
            return super()._get_menu_tab_domain(tab_id) & Domain("from_ai_automation", "=", False)
        if tab_id.startswith("ai-automation:"):
            agent_id = int(tab_id.split(":")[1])
            return (
                Domain("channel_type", "=", "ai_chat")
                & Domain("from_ai_automation", "=", True)
                & self._get_ai_agent_channels_domain(agent_id)
            )
        return super()._get_menu_tab_domain(tab_id)

    def _get_menu_tab_filter_domain(self, tab_id, filter_id):
        if tab_id.startswith("ai-automation:") and filter_id == "ai_automation_unread":
            return Domain("self_member_id.is_unread", "=", True)
        return super()._get_menu_tab_filter_domain(tab_id, filter_id)
