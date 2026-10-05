import { MessagingMenu } from "@mail/core/public_web/messaging_menu/messaging_menu";

import { useOnChange } from "@odoo/owl";

import { patch } from "@web/core/utils/patch";

patch(MessagingMenu.prototype, {
    setup() {
        super.setup(...arguments);
        useOnChange(
            () => [this.state().scopedAiAgentId, this.state().activeTab, this.visibleTabs.length],
            (scopedAiAgentId, activeTab) => {
                if (this.visibleTabs.some((tab) => tab.eq(activeTab))) {
                    return;
                }
                const fallback =
                    this.visibleTabs[0] ??
                    (scopedAiAgentId ? this.store.messagingMenu.scopedAiAgentTab : undefined);
                if (fallback) {
                    this.state().activeTab = fallback;
                }
            }
        );
    },
    get showAgentFilterDropdown() {
        return super.showAgentFilterDropdown && !this.state().scopedAiAgentId;
    },
    get visibleTabs() {
        const scopedAiAgentId = this.state().scopedAiAgentId;
        if (!scopedAiAgentId) {
            return super.visibleTabs;
        }
        const agent = this.store["ai.agent"].get(scopedAiAgentId);
        return agent?.has_automation_channels
            ? [this.store.messagingMenu.scopedAiAgentTab, this.store.messagingMenu.aiAutomationTab]
            : [];
    },
});
