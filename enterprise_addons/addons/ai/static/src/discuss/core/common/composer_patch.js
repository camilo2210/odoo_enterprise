import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";

patch(Composer.prototype, {
    get isAiAgentGenerating() {
        return Boolean(this.props.composer.targetThread?.channel?.isAiGenerating);
    },
    get isSendButtonDisabled() {
        return this.isAiAgentGenerating || super.isSendButtonDisabled;
    },
    async sendMessage() {
        if (this.isAiAgentGenerating) {
            return;
        }
        return super.sendMessage();
    },
});
