import { Message } from "@mail/core/common/message_model";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    /**
     * Agents messages logic:
     *   - comment -> verbose message
     *       - note: intermediary message (collapsed by default)
     *       - discussion: final message (always shown)
     *   - notification -> action taken
     *       - note: tool use (collapsed by default)
     *       - discussion: other (always shown)
     */
    get aiAgentAuthored() {
        return (
            this.channel_id?.ai_agent_id?.partner_id.eq(this.author_id) ||
            this.channel_id?.ai_session_ids.some((session) =>
                session.agent_id?.partner_id.eq(this.author_id),
            )
        );
    },
    get aiIsAgentStep() {
        return this.aiAgentAuthored && !this.isNotification && this.isNote;
    },
    get aiIsAgentResponse() {
        return this.aiAgentAuthored && !this.isNotification && this.isDiscussion;
    },
    get aiIsToolUse() {
        return this.aiAgentAuthored && this.isNotification && this.isNote;
    },
    get aiIsAction() {
        return this.aiAgentAuthored && this.isNotification && this.isDiscussion;
    },

    get notificationHidden() {
        // tool use have their own template, should not be shown as notifications
        return this.aiIsToolUse ? true : super.notificationHidden;
    },
});
