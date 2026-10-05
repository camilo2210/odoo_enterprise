import { Message } from "@mail/core/common/message_model";

import { AccountReportMessage } from "./message";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    onShowDeleteConfirm(owner) {
        super.onShowDeleteConfirm(...arguments);
        if (
            !(owner instanceof AccountReportMessage) ||
            !owner.accountReportProps.reportController
        ) {
            return;
        }
        owner.accountReportProps.reportController.removeAnnotation(this.id);
    },
});
