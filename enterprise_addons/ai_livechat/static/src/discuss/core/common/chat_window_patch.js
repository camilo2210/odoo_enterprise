import { ChatWindow } from "@mail/core/common/chat_window";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

patch(ChatWindow.prototype, {
    get showForwardOperatorButton() {
        const channel = this.props.chatWindow.channel;
        return channel.channel_type === "livechat" && channel.ai_agent_id;
    },

    async forwardOperator(ev) {
        let thread = this.props.chatWindow.channel.thread;
        if (this.channel.channel_type !== "livechat") {
            return;
        }
        // The livechat thread is persisted only after the first message is sent.
        if (thread.isTransient) {
            const channel = await this.store.env.services["im_livechat.livechat"].persist(thread);
            thread = channel.thread;
            if (!thread) {
                return;
            }
        }
        const result = await rpc("/ai_livechat/forward_operator", {
            channel_id: thread.id,
        });
        if (result["store_data"]) {
            this.store.insert(result["store_data"]);
        }
        if (result["notification"]) {
            this.store.env.services.notification.add(result["notification"], {
                type: result["notification_type"],
            });
        }
        if (result["success"] === true) {
            thread.resolveReadyToSwap();
        }
    },
});
