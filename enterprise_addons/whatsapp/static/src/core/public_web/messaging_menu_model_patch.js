import {
    MENU_TABS,
    MessagingMenu,
} from "@mail/core/public_web/messaging_menu/messaging_menu_model";
import { fields } from "@mail/model/export";

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

MENU_TABS.WHATSAPP = "whatsapp";

patch(MessagingMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.whatsappTab = fields.One("MessagingMenuTab", {
            compute() {
                if (this.store.self_user?.share !== false) {
                    return null;
                }
                return {
                    id: MENU_TABS.WHATSAPP,
                    icon: "oi_whatsapp",
                    sequence: 105,
                    label: _t("WhatsApp"),
                    emptyState: {
                        title: _t("No WhatsApp conversations yet."),
                    },
                    filters: [
                        {
                            id: "whatsapp_unread",
                            text: _t("Unread"),
                            includesChannel: (c) =>
                                Boolean(c.importantCounter ?? c.needactionCounter),
                        },
                    ],
                    includesChannel: (c) =>
                        c.channel_type === "whatsapp" &&
                        (c.self_member_id?.is_pinned || c.isLocallyPinned),
                    recordType: "discuss.channel",
                };
            },
            eager: true,
        });
    },
});
