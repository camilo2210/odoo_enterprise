import { STATIC_COG_GROUP_ACTION_CREATIVE } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class FolderActionNewFolder extends FolderAction {
    setup() {
        super.setup();
        this.label = _t("New Folder");
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.openDialogCreate(folder.id);
        await this.reload();
    }
}

export const folderActionNewFolder = {
    Component: FolderActionNewFolder,
    groupNumber: STATIC_COG_GROUP_ACTION_CREATIVE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.isEditable(folder)
        ),
};
