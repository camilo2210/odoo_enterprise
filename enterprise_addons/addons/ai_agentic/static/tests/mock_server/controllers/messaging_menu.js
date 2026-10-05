import { messagingMenuHelpers } from "@mail/../tests/mock_server/controllers/discuss/messaging_menu";

import { patch } from "@web/core/utils/patch";

// Mirrors `ai_agentic/controllers/messaging_menu.py` (AIAgenticMessagingMenuController):
// registers the Automation tab on top of the AI chat one.

patch(messagingMenuHelpers, {
    _get_menu_tab_domain(env, tab_id) {
        if (tab_id.startsWith("ai-automation:")) {
            // the mock discuss.channel has no `from_ai_automation` field:
            // the base ai_chat domain is close enough for the counters
            const agentId = Number(tab_id.split(":")[1]);
            return [
                ["channel_type", "=", "ai_chat"],
                ["ai_agent_id", "=", agentId],
            ];
        }
        return super._get_menu_tab_domain(env, tab_id);
    },
    _get_menu_tab_filter_domain(env, tab_id, filter_id) {
        if (tab_id.startsWith("ai-automation:") && filter_id === "ai_automation_unread") {
            return [["self_member_id.is_unread", "=", true]];
        }
        return super._get_menu_tab_filter_domain(env, tab_id, filter_id);
    },
});
