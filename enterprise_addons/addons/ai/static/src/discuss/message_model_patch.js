import { Message } from "@mail/core/common/message_model";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    /** Pending AI interaction associated with the newest incoming message. */
    get aiUserInputRequest() {
        if (
            !this.thread?.channel?.ai_agent_id ||
            this.isSelfAuthored ||
            !this.eq(this.thread.channel.newestMessage)
        ) {
            return undefined;
        }
        return this.thread.channel.aiInputSession?.userInputRequest;
    },
    get hasActions() {
        return !this.aiUserInputRequest && super.hasActions;
    },
});
