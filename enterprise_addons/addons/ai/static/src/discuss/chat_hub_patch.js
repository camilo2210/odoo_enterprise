import { ChatHub } from "@mail/core/common/chat_hub";
import { patch } from "@web/core/utils/patch";

patch(ChatHub.prototype, {
    get bubblesAttClass() {
        return {
            ...super.bubblesAttClass,
            "o-hasAiChat": this.chatHub.folded.some((chatWindow) => chatWindow.channel.isAiChat),
        };
    },
});
