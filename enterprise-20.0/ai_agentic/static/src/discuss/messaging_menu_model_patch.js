import {
    MENU_TABS,
    MessagingMenu,
} from "@mail/core/public_web/messaging_menu/messaging_menu_model";
import { fields } from "@mail/model/export";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";

MENU_TABS.AI_AUTOMATION = "ai-automation";

patch(MessagingMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.aiAutomationTab = fields.One("MessagingMenuTab", {
            compute() {
                const agentId = this.store.discuss.scopedAiAgentId;
                if (!agentId || !user.isInternalUser) {
                    return;
                }
                return {
                    id: `${MENU_TABS.AI_AUTOMATION}:${agentId}`,
                    icon: "flash_on",
                    iconClass: "d-inline-flex justify-content-center",
                    label: _t("Automation"),
                    sequence: 76,
                    recordType: "discuss.channel",
                    appWide: false,
                    includesChannel: (c) =>
                        this.store.discuss.scopedAiAgentId === agentId &&
                        c.isAiChat &&
                        c.from_ai_automation &&
                        c.ai_agent_id?.id === agentId,
                    filters: [
                        {
                            id: "ai_automation_unread",
                            text: _t("Unread"),
                            includesChannel: (c) => c.isUnread,
                        },
                    ],
                    emptyState: { title: _t("No automation runs yet.") },
                };
            },
            eager: true,
        });
        this.scopedAiAgentTab = fields.One("MessagingMenuTab", {
            compute() {
                const agentId = this.store.discuss.scopedAiAgentId;
                if (!agentId || !user.isInternalUser) {
                    return;
                }
                return {
                    id: `ai-chat:${agentId}`,
                    icon: "o_ai_icon",
                    iconClass: "d-inline-flex justify-content-center",
                    label: _t("AI"),
                    sequence: 75,
                    recordType: "discuss.channel",
                    appWide: false,
                    includesChannel: (c) =>
                        this.store.discuss.scopedAiAgentId === agentId &&
                        this.includesAiChatChannel(c) &&
                        c.ai_agent_id?.id === agentId,
                    filters: [
                        {
                            id: "ai_chat_unread",
                            text: _t("Unread"),
                            includesChannel: (c) => c.isUnread,
                        },
                    ],
                    emptyState: { title: _t("No AI Chats yet.") },
                };
            },
            eager: true,
        });
    },
    includesAiChatChannel(channel) {
        // automation runs live in their own tab
        return super.includesAiChatChannel(channel) && !channel.from_ai_automation;
    },
    async launchAiChat() {
        const scopedAiAgentId = this.store.discuss.scopedAiAgentId;
        if (!scopedAiAgentId) {
            return super.launchAiChat();
        }
        const result = await this.store.env.services.orm.call("ai.agent", "open_agent_chat", [
            scopedAiAgentId,
        ]);
        const channelId = Number(result.context.active_id.split("_").at(-1));
        const channel = await this.store["discuss.channel"].getOrFetch(channelId);
        channel?.setAsDiscussThread();
    },
});
