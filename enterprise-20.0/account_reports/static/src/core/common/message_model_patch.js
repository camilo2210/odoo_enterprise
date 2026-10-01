import { Message } from "@mail/core/common/message_model";

import { patch } from "@web/core/utils/patch";

/** @type {import("models").Message} */
const messagePatch = {
    setup() {
        super.setup(...arguments);
        /** @type {string|undefined} date the annotation was made for */
        this.account_reports_annotation_date = undefined;
    },
};
patch(Message.prototype, messagePatch);
