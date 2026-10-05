import { Thread } from "@mail/core/common/thread";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    get showVisitorDisconnected() {
        return !this.channel?.livechat_social_account_id && super.showVisitorDisconnected;
    },
});
