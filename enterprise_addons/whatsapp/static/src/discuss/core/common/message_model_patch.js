import { Message } from "@mail/core/common/message_model";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").Message} */
const messagePatch = {
    setup() {
        super.setup(...arguments);
        /** @type {string|undefined} state of the related whatsapp message */
        this.whatsappStatus = undefined;
    },
    get editable() {
        if (this.channel_id?.channel_type === "whatsapp") {
            return false;
        }
        return super.editable;
    },
    /** @override */
    get canReplyTo() {
        return (
            super.canReplyTo &&
            (this.channel_id?.channel_type !== "whatsapp" ||
                !this.thread?.composer?.whatsappThreadDisabled)
        );
    },
    get isTranslatable() {
        return (
            super.isTranslatable ||
            (this.store.hasMessageTranslationFeature &&
                this.channel_id?.channel_type === "whatsapp" &&
                this.store.self_user?.share === false)
        );
    },
    showSeenIndicator(thread) {
        return super.showSeenIndicator(thread) && this.whatsappStatus !== "error";
    },
};
patch(Message.prototype, messagePatch);
