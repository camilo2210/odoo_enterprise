import { STATIC_COG_GROUP_ACTION_DESTRUCTIVE } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class FolderActionArchive extends FolderAction {
    setup() {
        super.setup();
        this.icon = "delete";
        this.iconClass = "oi-filled";
        this.label = _t("Trash");
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.moveToTrash(folder.id);
        await this.reload();
    }
}

/** @type folderAction */
export const folderActionArchive = {
    Component: FolderActionArchive,
    groupNumber: STATIC_COG_GROUP_ACTION_DESTRUCTIVE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(
            env,
            target,
            ({ folder, documentService }) =>
                documentService.userIsInternal && documentService.isEditable(folder)
        ),
};
