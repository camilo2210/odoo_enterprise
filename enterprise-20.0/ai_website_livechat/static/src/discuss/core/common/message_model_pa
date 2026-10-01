import { Message } from "@mail/core/common/message_model";
import { fields } from "@mail/model/export";

import { patch } from "@web/core/utils/patch";

import "./ai_record_previews_model";

/** @type {import("models").Message} */
const messagePatch = {
    setup() {
        super.setup(...arguments);
        this.ai_record_previews = fields.One("ai.record.previews", {
            inverse: "message_id",
            onDelete: (recordPreviews) => recordPreviews?.delete(),
        });
    },
};

patch(Message.prototype, messagePatch);
