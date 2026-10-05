import { STATIC_COG_GROUP_ACTION_ORGANIZE } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentsCogMenuItemStar extends FolderAction {
    setup(isAdd) {
        super.setup();
        this.icon = "star";
        this.iconClass = isAdd ? "" : "oi-filled";
        this.label = isAdd ? _t("Add star") : _t("Remove star");
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.toggleFavorites([folder.id]);
    }
}

export class DocumentsCogMenuItemStarAdd extends DocumentsCogMenuItemStar {
    setup() {
        super.setup(true);
    }
}

export class DocumentsCogMenuItemStarRemove extends DocumentsCogMenuItemStar {
    setup() {
        super.setup(false);
    }
}

/** @type folderAction */
export const folderActionStar = {
    Component: DocumentsCogMenuItemStarAdd,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(
            env,
            target,
            ({ folder, documentService }) =>
                documentService.isEditable(folder) && !folder.is_favorited
        ),
};

/** @type folderAction */
export const folderActionStarRemove = {
    Component: DocumentsCogMenuItemStarRemove,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(
            env,
            target,
            ({ folder, documentService }) =>
                documentService.isEditable(folder) && folder.is_favorited
        ),
};
