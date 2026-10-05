import { Message } from "@mail/core/common/message_model";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    get authorName() {
        const ret = super.authorName;
        if (this.isSentBySocialPage) {
            // there's no author when we fetch the old messages
            return this.author_id || this.author_guest_id
                ? `${this.channel_id.livechat_social_account_id.name} (${ret})`
                : this.channel_id.livechat_social_account_id.name;
        }
        return ret;
    },

    get authorAvatarUrl() {
        if (this.isSentBySocialPage) {
            return this.channel_id.social_account_image_url;
        }
        return super.authorAvatarUrl;
    },

    /**
     * Don't allow editing messages sent on social media.
     */
    get editable() {
        if (this.channel_id?.livechat_social_account_id) {
            return false;
        }
        return super.editable;
    },

    /**
     * Whether the message has been sent on the social media by the page.
     */
    get isSentBySocialPage() {
        return (
            this.message_type === "comment" &&
            this.channel_id?.livechat_social_account_id &&
            !this.author_guest_id?.in(this.channel_id.livechat_customer_guest_ids)
        );
    },
});
