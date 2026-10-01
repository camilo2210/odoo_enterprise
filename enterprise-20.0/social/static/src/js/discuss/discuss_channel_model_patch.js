import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { fields } from "@mail/model/export";
import { patch } from "@web/core/utils/patch";

patch(DiscussChannel.prototype, {
    setup() {
        super.setup(...arguments);
        this.livechat_customer_guest_ids = fields.Many("mail.guest");
        this.livechat_social_account_id = fields.One("social.account");
        /** @type {string} URL of the profile picture of the social account */
        this.social_account_image_url = undefined;
        /** @type {string} URL of the icon of the social media */
        this.social_account_media_image_url = undefined;
        this.livechat_failure = undefined;
        this.onChange(
            () => [this.livechat_failure],
            function onChangeLivechatFailure(livechatFailure) {
                if (
                    this.livechat_social_account_id &&
                    livechatFailure === "no_agent" &&
                    !this.livechat_end_dt
                ) {
                    // force the channel to be visible even without being member
                    this.isLocallyPinned = true;
                }
            },
            { immediate: true }
        );
    },

    get computedDisplayName() {
        if (this.livechat_social_account_id) {
            return this.name;
        }
        return super.computedDisplayName;
    },

    get hasCorrespondentAvatar() {
        return this.livechat_social_account_id || super.hasCorrespondentAvatar;
    },

    get allowCalls() {
        return !this.livechat_social_account_id && super.allowCalls;
    },
});
