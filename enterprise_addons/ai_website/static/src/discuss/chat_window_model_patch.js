import { ChatWindow } from "@mail/core/common/chat_window_model";
import { patch } from "@web/core/utils/patch";
import { aiChannelBus } from "@ai/utils/ai_channel_bus";
import {
    AI_WEBSITE_ELEMENT_SELECTION_COMMAND,
    isAiWebsiteBuilderChannel,
} from "@ai_website/utils";

patch(ChatWindow.prototype, {
    fold() {
        if (isAiWebsiteBuilderChannel(this.channel)) {
            aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_COMMAND, {
                type: "stop_picker",
            });
        }
        return super.fold(...arguments);
    },
    _onClose() {
        const isAiWebsiteBuilder = isAiWebsiteBuilderChannel(this.channel);
        super._onClose(...arguments);
        if (isAiWebsiteBuilder) {
            aiChannelBus.trigger(AI_WEBSITE_ELEMENT_SELECTION_COMMAND, { type: "release" });
        }
    },
});
