import { messagingMenuHelpers } from "@mail/../tests/mock_server/controllers/discuss/messaging_menu";

import { patch } from "@web/core/utils/patch";

// Mirrors `ai/controllers/messaging_menu.py` (AIMessagingMenuController): registers the
// AI chat tab, on top of mail/discuss's tabs.

patch(messagingMenuHelpers, {
    _get_menu_tab_domain(env, tab_id) {
        if (!tab_id.startsWith("ai-chat")) {
            return super._get_menu_tab_domain(env, tab_id);
        }
        const domain = [["channel_type", "=", "ai_chat"]];
        if (tab_id.includes(":")) {
            domain.push(["ai_agent_id", "=", Number(tab_id.split(":")[1])]);
        }
        return domain;
    },
    _get_menu_tab_filter_domain(env, tab_id, filter_id) {
        if (tab_id.startsWith("ai-chat") && filter_id === "ai_chat_unread") {
            return [["self_member_id.is_unread", "=", true]];
        }
        if (tab_id === "ai-chat" && filter_id.startsWith("ai_agent:")) {
            const agentId = Number(filter_id.split(":")[1]);
            return [["ai_agent_id", "=", agentId]];
        }
        return super._get_menu_tab_filter_domain(env, tab_id, filter_id);
    },
});
