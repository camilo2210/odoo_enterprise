import { ChatWindow } from "@mail/core/common/chat_window_model";
import { patch } from "@web/core/utils/patch";

patch(ChatWindow.prototype, {
    _onClose(options = {}) {
        const channel = this.channel;
        super._onClose(...arguments);
        if (channel) {
            this.store.env.bus.trigger("CHATWINDOW_CLOSED", { channel });
        }
    },
});
