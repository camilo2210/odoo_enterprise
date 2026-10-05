import { NotificationMessage } from "@mail/core/common/notification_message";
import { patch } from "@web/core/utils/patch";

patch(NotificationMessage.prototype, {
    get showDate() {
        return this.props.message?.aiAgentAuthored ? false : super.showDate;
    },
    get showInlineBody() {
        return this.message.notificationType == "ai_note" ? true : super.showInlineBody;
    },
});
