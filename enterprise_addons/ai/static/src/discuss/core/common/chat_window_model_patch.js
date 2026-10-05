import { patch } from "@web/core/utils/patch";
import { ChatWindow } from "@mail/core/common/chat_window_model";

patch(ChatWindow.prototype, {
    computeCanShow() {
        if (this.store.aiInsertButtonTarget && this.store.discuss.isActive) {
            return this.channel.isAiChat;
        }
        return super.computeCanShow();
    },
    async _onBeforeClose() {
        // override of _onBeforeClose not _onClose because the latter is called from each tab
        if (this.channel.isAiChat) {
            this.channel.update({
                // clear localStorage before delete
                ai_prompt_buttons: [],
                // Allow write on localStorage, in case the closing happens outside of the tab that
                // created the channel.
                are_prompts_from_local_storage: false,
            });
            if (this.channel.isLoaded && !this.channel.hasLoadingFailed && this.channel.isEmpty) {
                await this.channel.deleteAiChatRpc();
            }
        }
        return await super._onBeforeClose(...arguments);
    },
});
