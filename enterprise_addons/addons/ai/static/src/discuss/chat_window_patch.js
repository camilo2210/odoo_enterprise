import { ChatWindow } from "@mail/core/common/chat_window";
import { patch } from "@web/core/utils/patch";

patch(ChatWindow.prototype, {
    get attClass() {
        return {
            ...super.attClass,
            "o-isAiComposer": this.channel.isAiChat,
        };
    },
    get showAiPreviousChatSuggestion() {
        return (
            this.channel.isAiChat &&
            this.channel.isEmpty &&
            this.channel.suggestedAiChannel?.exists() &&
            !this.channel.suggestedAiChannel.chatWindow?.isOpen
        );
    },
    dismissAiPreviousChatSuggestion() {
        this.channel.suggestedAiChannel = undefined;
    },
    async reopenSuggestedAiChannel() {
        const currentChatWindow = this.props.chatWindow;
        const suggestedChannel = this.channel.suggestedAiChannel;
        this.dismissAiPreviousChatSuggestion();
        if (this.channel.exists() && this.channel.isEmpty) {
            await currentChatWindow.requestClose();
        }
        await suggestedChannel.openChatWindow({ focus: true });
    },
});
