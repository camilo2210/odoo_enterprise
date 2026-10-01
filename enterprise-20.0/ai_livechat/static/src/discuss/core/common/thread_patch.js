import { Thread } from "@mail/core/common/thread";
import { patch } from "@web/core/utils/patch";

// AI chats in frontend do not share the backend's design. Hide steps from frontend
patch(Thread.prototype, {
    get orderedMessages() {
        if (this.channel?.ai_agent_id && this.props.thread?.aiFromFrontend) {
            return super.orderedMessages.filter((msg) => !(msg.aiIsAgentStep || msg.aiIsToolUse));
        }
        return super.orderedMessages;
    },
});
