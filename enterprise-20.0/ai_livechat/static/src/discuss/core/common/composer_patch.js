import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";

patch(Composer.prototype, {
    get supportedFileTypes() {
        if (this.thread?.channel?.ai_agent_id) {
            // indexable files and image types supported by most AI providers
            return "text/*,application/pdf,.docx,.pptx,.xlsx,.opendoc,.png,.jpg,.jpeg,.webp,.gif";
        }
        return super.supportedFileTypes;
    },
});
