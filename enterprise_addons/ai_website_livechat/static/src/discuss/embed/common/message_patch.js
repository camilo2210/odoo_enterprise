import { Message } from "@mail/core/common/message";
import { AIRecordsPreview } from "@ai_website_livechat/discuss/core/common/preview_records/ai_records_preview";
import { patch } from "@web/core/utils/patch";

Message.components = { ...Message.components, AIRecordsPreview };

patch(Message.prototype, {
    get hasRecordPreviews() {
        return Boolean(this.props.message?.ai_record_previews?.preview_sets?.length);
    },
});
