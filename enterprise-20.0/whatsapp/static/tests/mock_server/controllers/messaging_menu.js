import { messagingMenuHelpers } from "@mail/../tests/mock_server/controllers/discuss/messaging_menu";

import { patch } from "@web/core/utils/patch";

// Mirrors `whatsapp/controller/messaging_menu.py` (WhatsappMessagingMenuController):
// registers the whatsapp tab, on top of mail/discuss's tabs.

patch(messagingMenuHelpers, {
    _get_menu_tab_domain(env, tab_id) {
        if (tab_id === "whatsapp") {
            return [
                ["channel_type", "=", "whatsapp"],
                ["self_member_id.is_pinned", "=", true],
            ];
        }
        return super._get_menu_tab_domain(env, tab_id);
    },
    _get_menu_tab_filter_domain(env, tab_id, filter_id) {
        if (tab_id === "whatsapp" && filter_id === "whatsapp_unread") {
            return [["self_member_id.is_unread", "=", true]];
        }
        return super._get_menu_tab_filter_domain(env, tab_id, filter_id);
    },
});
