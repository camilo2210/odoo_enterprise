import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(DiscussChannel.prototype, {
    get allowedToRenameChannelTypes() {
        return [...super.allowedToRenameChannelTypes, "ai_chat"];
    },
    get hasDeletedAiAgent() {
        return this.isAiChat && !this.ai_agent_id;
    },
    get composerHidden() {
        if (this.hasDeletedAiAgent || this.aiSessionAwaitsResponse) {
            return true;
        }
        return super.composerHidden;
    },
    get composerHiddenText() {
        if (this.hasDeletedAiAgent) {
            return _t("This session's AI agent has been deleted.");
        }
        if (this.aiSessionAwaitsResponse) {
            return "";
        }
        return super.composerHiddenText;
    },
    get aiSessionAwaitsResponse() {
        return this.ai_session_ids.some(
            (session) => session.userInputRequest || session.external_pending_tool,
        );
    },
});
