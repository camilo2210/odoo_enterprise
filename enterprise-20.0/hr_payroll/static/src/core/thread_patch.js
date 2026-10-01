import { proxy } from "@odoo/owl";
import { Thread } from "@mail/core/common/thread";
import { patch } from "@web/core/utils/patch";
import { useBus, useService } from "@web/core/utils/hooks";
import { SIZES } from "@web/core/ui/ui_utils";

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        this.multiHighlightState = proxy({ messageIds: [] });
        this.ui = useService("ui");

        useBus(this.env.bus, "HR_PAYROLL:HIGHLIGHT_MESSAGES", (event) => {
            const { threadModel, threadId, dateToReview } = event.detail;
            if (this.props.thread.model === threadModel && this.props.thread.id === threadId) {
                this.highlightMessagesSinceDate(dateToReview);
            }
        });

        useBus(this.env.bus, "HR_PAYROLL:CLEAR_HIGHLIGHTS", (event) => {
            const { threadModel, threadId } = event.detail;
            if (this.props.thread.model === threadModel && this.props.thread.id === threadId) {
                this.clearHighlights();
            }
        });
    },

    getMessageClassName(message) {
        const baseClass = super.getMessageClassName(message);
        if (!message.isNotification && this.multiHighlightState.messageIds.includes(message.id)) {
            return "bg-warning-subtle";
        }
        return baseClass;
    },

    highlightMessagesSinceDate(dateToReview) {
        if (!dateToReview) {
            this.multiHighlightState.messageIds = [];
            return;
        }

        const searchDate = dateToReview.minus({ seconds: 10 });
        const messages = this.props.thread.messages || [];
        const messageIds = messages
            .filter(msg => msg.message_type === "tracking" && msg.datetime >= searchDate)
            .map(msg => msg.id);

        this.multiHighlightState.messageIds = messageIds;

        if (this.ui.size >= SIZES.XL && this.messageHighlight && messageIds.length > 0) {
            this.props.thread.loadAround({ messageId: messageIds[messageIds.length - 1] });
            this.messageHighlight.highlightedMessageId = messageIds[messageIds.length - 1];
        }
    },

    clearHighlights() {
        this.multiHighlightState.messageIds = [];
        if (this.messageHighlight) {
            this.messageHighlight.clear();
        }
    },
});
