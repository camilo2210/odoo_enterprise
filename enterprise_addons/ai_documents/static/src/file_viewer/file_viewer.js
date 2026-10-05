import { FileViewer as WebFileViewer } from "@web/core/file_viewer/file_viewer";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";


patch(WebFileViewer.prototype, {
    async openAIChat() {
        if (this.documentService) {
            if (this.state.file.isVideo || this.state.file.isUrlYoutube) {
                this.notification.add(_t("Oops, AI cannot process videos!"), { type: "warning" });
                return;
            }
            const fileName = this.state.file.name || 'File Attachment';
            await this.aiChatLauncher.launchAIChat({
                interfaceKey: "file_viewer_ai_button",
                recordModel: "ir.attachment",
                recordId: this.state.file.documentData.attachment_id.id,
                channelTitle: fileName,
                aiChatSourceId: this.state.file.documentData.attachment_id.id,
            });
        } else {
            return super.openAIChat();
        }
    },
});
