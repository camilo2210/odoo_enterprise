import { DiscussAvatar } from "@mail/core/common/discuss_avatar";
import { patch } from "@web/core/utils/patch";

patch(DiscussAvatar.prototype, {
    get showIconMask() {
        return !this.channel?.livechat_social_account_id && super.showIconMask;
    },
});
