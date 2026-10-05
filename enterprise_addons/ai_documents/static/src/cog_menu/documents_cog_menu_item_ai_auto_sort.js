import { FolderAction } from "@documents/views/action/folder_action";

export class DocumentsCogMenuItemAiAutoSort extends FolderAction {
    static template = "ai_documents.DocumentsCogMenuItemAiAutoSort";

    setup() {
        super.setup();
        this.folder = this.env.searchModel.getSelectedFolder();
    }

    async onSelected() {
        if (!this.folder || typeof this.folder.id !== "number") {
            return;
        }

        await this.action.doAction("ai_documents.ai_documents_sort_action", {
            additionalContext: {
                default_folder_id: this.folder.id,
            },
            onClose: async () => {
                await this.env.searchModel._reloadSearchPanel();
            },
        });
    }
}
