import { Message } from "@mail/core/common/message";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    get attClass() {
        const attClass = super.attClass;
        attClass["o-ai-agent-response"] = this.props.message.aiIsAgentResponse;
        attClass["ps-2"] = this.isAIMessage && this.env.inChatWindow;
        return attClass;
    },
    get bodyAttClass() {
        const bodyAttClass = super.bodyAttClass;
        bodyAttClass["px-2"] = this.isAIMessage;
        bodyAttClass["text-muted"] = this.props.message.aiIsAgentStep;
        return bodyAttClass;
    },
    get quickActionCount() {
        return this.props.thread?.channel?.isAiChat ? 3 : super.quickActionCount;
    },
    getAvatarContainerAttClass() {
        const res = super.getAvatarContainerAttClass();
        if (this.props.thread?.channel?.isAiChat) {
            return {
                ...res,
                "mx-1": this.env.inChatWindow,
                "mx-2": !this.env.inChatWindow,
            };
        }
        return res;
    },
    get isAlignedRight() {
        return (
            (this.props.thread?.channel?.isAiChat && this.props.message.isSelfAuthored) ||
            super.isAlignedRight
        );
    },
    get isAIMessage() {
        return this.props.message.aiAgentAuthored;
    },
    /**
     * @override
     * @param {HTMLElement} bodyEl
     */
    prepareMessageBody(bodyEl) {
        super.prepareMessageBody(...arguments);
        if (!bodyEl) {
            return;
        }
        const codeBlocks = bodyEl.querySelectorAll("pre code");
        for (const block of codeBlocks) {
            if (window.Prism) {
                window.Prism.highlightElement(block, false);
            }
        }
    },
});
