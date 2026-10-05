import { STATIC_COG_GROUP_ACTION_ACCESS } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentsCogMenuItemShare extends FolderAction {
    setup() {
        super.setup();
        this.icon = "share";
        this.label = _t("Share");
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.openSharingDialog([folder.id]);
    }
}

/** @type folderAction */
export const folderActionShare = {
    Component: DocumentsCogMenuItemShare,
    groupNumber: STATIC_COG_GROUP_ACTION_ACCESS,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(
            env,
            target,
            ({ folder, documentService }) =>
                documentService.userIsInternal && documentService.isFolderSharable(folder)
        ),
};
