import { ChannelMember } from "@mail/discuss/core/common/channel_member_model";
import { patch } from "@web/core/utils/patch";

patch(ChannelMember.prototype, {
    get imStatusUI() {
        if (this.channel_id.livechat_social_account_id && this.guest_id) {
            return undefined;
        }
        return super.imStatusUI;
    },
});
