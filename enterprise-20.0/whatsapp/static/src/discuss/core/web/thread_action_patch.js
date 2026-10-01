import { patch } from "@web/core/utils/patch";
import { ThreadAction } from "@mail/core/common/thread_actions";

patch(ThreadAction.prototype, {
    _condition({ action, channel, owner, store }) {
        if (
            channel?.channel_type === "whatsapp" &&
            action.id === "advanced-settings" &&
            channel.whatsapp_partner_id?.notEq(store.self_user?.partner_id) &&
            !owner.isDiscussContent
        ) {
            return true;
        }
        return super._condition(...arguments);
    },
});
