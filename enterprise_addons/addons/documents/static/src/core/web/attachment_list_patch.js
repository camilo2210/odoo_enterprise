import { AttachmentList } from "@mail/core/common/attachment_list";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(AttachmentList.prototype, {
    setup() {
        super.setup();
        this.documentService = useService("document.document");
        this.notification = useService("notification");
    },

    getActions(attachment) {
        const res = super.getActions(...arguments);
        if (this.documentService.canAddAttachmentToDocuments(attachment)) {
            res.push({
                label: attachment.documentHelperText,
                icon: attachment.documentIcon,
                onSelect: () => this.documentService.onClickAddAttachmentToDocuments(attachment),
            });
        }
        return res;
    },

    hasUnlinkConfirmation(attachment) {
        // Avoid confirmation dialog as the attachment is only removed from the chatter but kept in Documents
        return !attachment.linked_document_id;
    },

    async onConfirmUnlink(attachments) {
        const hasNotification = attachments.some(
            (attachment) => !this.hasUnlinkConfirmation(attachment)
        );
        await super.onConfirmUnlink(attachments);
        if (hasNotification) {
            this.notification.add(_t("Attachment removed. Linked document moved to Trash."), {
                type: "info",
            });
        }
    },
});
