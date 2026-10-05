import { FileViewer as WebFileViewer } from "@web/core/file_viewer/file_viewer";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";


patch(WebFileViewer.prototype, {
    setup() {
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
        this.notification = useService("notification");
    },

    async openAIChat() {
        if (this.state.file.isVideo || this.state.file.isUrlYoutube) {
            this.notification.add(_t("Oops, AI cannot process videos!"), { type: "warning" });
            return;
        }
        const fileName = this.state.file.name || 'File Attachment';
        await this.aiChatLauncher.launchAIChat({
            interfaceKey: "file_viewer_ai_button",
            recordModel: "ir.attachment",
            recordId: this.state.file.id,
            channelTitle: fileName,
            aiChatSourceId: this.state.file.id,
        });
    },
});
