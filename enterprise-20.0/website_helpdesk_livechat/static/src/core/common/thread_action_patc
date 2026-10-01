import { patch } from "@web/core/utils/patch";
import { ThreadAction } from "@mail/core/common/thread_actions";

patch(ThreadAction.prototype, {
    _condition({ action, channel, owner, store }) {
        if (
            action.id === "create-ticket" &&
            store.helpdesk_livechat_active &&
            channel?.channel_type === "livechat" &&
            store.has_access_create_ticket &&
            !owner.isDiscussSidebarChannelActions
        ) {
            return true;
        }
        return super._condition(...arguments);
    },
});
