import { messagingMenuHelpers } from "@mail/../tests/mock_server/controllers/discuss/messaging_menu";

import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";

// Mirrors `social/controllers/messaging_menu.py` (SocialLivechatMessagingMenuController):
// adds the social conversations waiting for an operator to the livechat tab.

patch(messagingMenuHelpers, {
    _get_menu_tab_domain(env, tab_id) {
        const domain = super._get_menu_tab_domain(env, tab_id);
        if (tab_id !== "livechat") {
            return domain;
        }
        return Domain.or([
            domain,
            [
                ["livechat_social_account_id", "!=", false],
                ["livechat_failure", "=", "no_agent"],
                ["livechat_end_dt", "=", false],
            ],
        ]).toList();
    },
});
