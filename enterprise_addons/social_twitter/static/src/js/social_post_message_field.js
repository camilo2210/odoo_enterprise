import { SocialPostMessageField } from "@social/js/fields/social_post_message_field";
import { patch } from "@web/core/utils/patch";
import { computed } from "@odoo/owl";

/**
 * Twitter has its own way to count chars.
 */
patch(SocialPostMessageField.prototype, {
    setup() {
        super.setup();
        this.twitterCount = computed(() => this.computeMessageSize(this.messageValue()));
    },

    computeMessageSize(message) {
        // URL count as 23 chars
        // emoji count as 2 chars (some emoji like `'🙂'.length` will return already 2,
        // but eg `'❤'.length` will be 1 without replacing)
        return (message || "")
            .replace(/\bhttps?:\/\/[^\s]+/gi, "_".repeat(23))
            .replace(/\p{Extended_Pictographic}/gu, "__").length;
    },

    get remainingCharsPerMedia() {
        const count = super.remainingCharsPerMedia;
        return count.map(({ mediaId, mediaType, remainingCount }) => ({
            mediaId,
            mediaType,
            remainingCount:
                mediaType === "twitter" ? 280 - this.twitterCount() : remainingCount,
        }));
    },
});
