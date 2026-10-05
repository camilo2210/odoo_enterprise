import { DiscussApp } from "@mail/core/public_web/discuss_app/discuss_app_model";

import { patch } from "@web/core/utils/patch";

patch(DiscussApp.prototype, {
    setup() {
        super.setup(...arguments);
        this.scopedAiAgentId = undefined;
    },

    setScopedAiAgent(id) {
        const agentId = Number(id);
        if (agentId !== this.scopedAiAgentId) {
            this.scopedAiAgentId = agentId;
            this.sidebarState.activeTab = this.store.messagingMenu.scopedAiAgentTab;
        }
    },

    clearScopedAiAgent() {
        this.scopedAiAgentId = undefined;
    },

    get scopedAgent() {
        return this.scopedAiAgentId ? this.store["ai.agent"].get(this.scopedAiAgentId) : undefined;
    },

    isChannelInScopedAiAgent(channel) {
        return Boolean(this.scopedAiAgentId) && channel?.ai_agent_id?.id === this.scopedAiAgentId;
    },
});
