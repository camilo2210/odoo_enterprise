import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

/**
 * This patch ensures that stat buttons of a view are  refreshed
 * when a new attachment is added or a message is posted,
 * specifically for models that inherit `documents.mixin`.
 */
const chatterPatch = {
    async setup() {
        super.setup(...arguments);
        this.store = useService("mail.store");
    },
    get hasParentReloadOnMessagePosted() {
        return super.hasParentReloadOnMessagePosted || this.thread().is_documents_mixin;
    },
    get hasParentReloadOnAttachmentsChanged() {
        return super.hasParentReloadOnAttachmentsChanged || this.thread().is_documents_mixin;
    },
};
patch(Chatter.prototype, chatterPatch);
