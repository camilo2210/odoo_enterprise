import { DiscussAvatar } from "@mail/core/common/discuss_avatar";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu/messaging_menu";
import { MENU_TABS } from "@mail/core/public_web/messaging_menu/messaging_menu_model";

import { useOnChange } from "@odoo/owl";

import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { patch } from "@web/core/utils/patch";

MessagingMenu.components = { ...MessagingMenu.components, CheckboxItem, Dropdown, DiscussAvatar };

patch(MessagingMenu.prototype, {
    setup() {
        super.setup(...arguments);
        // Opening a chat from another agent should clear the filter.
        useOnChange(
            () => [this.store.discuss.thread],
            (thread) => {
                const selectedAgentFilter = this.state().selectedAgentFilter;
                if (selectedAgentFilter && !thread?.channel?.ai_agent_id?.eq(selectedAgentFilter)) {
                    this.state().selectedAgentFilter = undefined;
                }
            },
            { initialRun: false }
        );
    },
    get isAiChatTab() {
        return this.activeTab().id === MENU_TABS.AI_CHAT;
    },
    get isAgentFilterActive() {
        return Boolean(this.state().selectedAgentFilter);
    },
    isAgentSelected(agent) {
        return Boolean(this.state().selectedAgentFilter?.eq(agent));
    },
    get showAgentFilterDropdown() {
        return this.isAiChatTab && this.state().isSidebar && this.chatAgents.length > 0;
    },
    get chatAgents() {
        const agents = this.store.messagingMenu.aiChatTab.channels
            .map((channel) => channel.ai_agent_id)
            .filter(Boolean);
        return [...new Map(agents.map((agent) => [agent.id, agent])).values()];
    },
    selectAgentFilter(agent) {
        this.state().selectedAgentFilter = agent;
    },
});
