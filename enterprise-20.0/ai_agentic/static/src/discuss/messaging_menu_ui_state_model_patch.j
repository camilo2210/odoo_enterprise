import { MessagingMenuUIState } from "@mail/core/public_web/messaging_menu/messaging_menu_ui_state_model";

import { patch } from "@web/core/utils/patch";

patch(MessagingMenuUIState.prototype, {
    /**
     * Agent scoping only applies to the Discuss sidebar, not the systray popover. Feeds
     * `MessagingMenuUIState.aiChatAgentId` which narrows the AI tab through the same flow
     * as the dropdown.
     */
    get scopedAiAgentId() {
        return this.isSidebar ? this.store.discuss.scopedAiAgentId : false;
    },
});
