import { STATIC_COG_GROUP_ACTION_ORGANIZE } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class FolderActionRename extends FolderAction {
    setup() {
        super.setup();
        this.label = _t("Rename");
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.openDocumentFormDialog({ documentId: folder.id });
        await this.reload();
    }
}

export const folderActionRename = {
    Component: FolderActionRename,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.isEditable(folder)
        ),
};
