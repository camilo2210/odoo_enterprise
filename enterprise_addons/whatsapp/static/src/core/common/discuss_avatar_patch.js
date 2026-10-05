import { DiscussAvatar } from "@mail/core/common/discuss_avatar";
import { patch } from "@web/core/utils/patch";

patch(DiscussAvatar.prototype, {
    get showIcon() {
        return (
            super.showIcon || this.channelMember?.eq(this.channelMember.channel_id.whatsappMember)
        );
    },
});
