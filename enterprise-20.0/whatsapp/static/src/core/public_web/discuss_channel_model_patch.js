import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").DiscussChannel} */
const discussChannelPatch = {
    get autoOpenChatWindowOnNewMessage() {
        return this.channel_type === "whatsapp" || super.autoOpenChatWindowOnNewMessage;
    },
    showThreadIcon(...args) {
        return this.channel_type === "whatsapp" || super.showThreadIcon(...args);
    },
};
patch(DiscussChannel.prototype, discussChannelPatch);
