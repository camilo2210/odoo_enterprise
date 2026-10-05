import { ChannelMember } from "@mail/discuss/core/common/channel_member_model";
import { fields } from "@mail/model/export";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").ChannelMember} */
const channelMemberPatch = {
    setup() {
        super.setup(...arguments);
        this.isAiResponding = fields.Attr(false, {
            compute() {
                if (!this.isAiAgent) {
                    return false;
                }
                const channel = this.channel_id;
                return Boolean(
                    channel?.channel_type === "livechat" &&
                        !channel.aiInputSession?.userInputRequest &&
                        channel.isAiGenerating &&
                        !channel.ai_session_ids.some((session) => session.external_pending_tool),
                );
            },
            eager: true,
        });
        this.onChange(
            () => [this.isAiResponding],
            function onChangeIsAiResponding(isAiResponding) {
                if (this.isAiAgent) {
                    this.isTyping = isAiResponding;
                }
            },
            { immediate: true, initialRun: false },
        );
    },
    get isAiAgent() {
        return Boolean(this.channel_id?.ai_agent_id?.partner_id?.eq(this.partner_id));
    },
    registerTypingTimeout() {
        // no typing timeout for agent as it's used to show the current ai tool being used
        if (this.isAiAgent) {
            return;
        }
        return super.registerTypingTimeout();
    },
};
patch(ChannelMember.prototype, channelMemberPatch);
