import { MENU_TABS } from "@mail/core/public_web/messaging_menu/messaging_menu_model";
import { MessagingMenuUIState } from "@mail/core/public_web/messaging_menu/messaging_menu_ui_state_model";
import { fields } from "@mail/model/export";

import { patch } from "@web/core/utils/patch";

patch(MessagingMenuUIState.prototype, {
    setup() {
        super.setup(...arguments);
        this.selectedAgentFilter = fields.One("ai.agent");
        this.onChange(
            () => [this.aiChatAgentId],
            function onChangeAiChatAgentId(aiChatAgentId) {
                if (this.activeTab?.id !== MENU_TABS.AI_CHAT) {
                    this.selectedAgentFilter = null;
                }
                this.setPluginFilter(
                    "ai.agent_scope",
                    aiChatAgentId
                        ? {
                              id: `ai_agent:${aiChatAgentId}`,
                              includesChannel: (c) => c.ai_agent_id?.id === aiChatAgentId,
                          }
                        : null
                );
            },
            { immediate: true, initialRun: false }
        );
    },
    get aiChatAgentId() {
        return this.activeTab?.id === MENU_TABS.AI_CHAT && this.selectedAgentFilter
            ? this.selectedAgentFilter.id
            : null;
    },
    get isSidebar() {
        return this.id === "discuss.sidebar";
    },
});
