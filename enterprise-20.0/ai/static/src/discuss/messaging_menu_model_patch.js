import {
    MENU_TABS,
    MessagingMenu,
} from "@mail/core/public_web/messaging_menu/messaging_menu_model";
import { fields } from "@mail/model/export";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";

MENU_TABS.AI_CHAT = "ai-chat";

patch(MessagingMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.aiChatTab = fields.One("MessagingMenuTab", {
            compute() {
                if (!user.isInternalUser) {
                    return;
                }
                return {
                    id: MENU_TABS.AI_CHAT,
                    icon: "o_ai_icon",
                    iconClass: "d-inline-flex justify-content-center",
                    label: _t("AI"),
                    sequence: 75,
                    recordType: "discuss.channel",
                    includesChannel: (c) => this.includesAiChatChannel(c),
                    filters: [
                        {
                            id: "ai_chat_unread",
                            text: _t("Unread"),
                            includesChannel: (c) => c.isUnread,
                        },
                    ],
                    actions: [
                        {
                            id: "new-ai-chat",
                            icon: "add",
                            text: _t("Chat"),
                            onClick: () => this.launchAiChat(),
                        },
                    ],
                    emptyState: { title: _t("No AI Chats yet.") },
                };
            },
            eager: true,
        });
    },
    includesAiChatChannel(channel) {
        return channel.isAiChat;
    },
    launchAiChat() {
        return this.store.env.services.aiChatLauncher.launchAIChat({
            interfaceKey: "systray_ai_button",
        });
    },
});
