import { STATIC_COG_GROUP_ACTION_ORGANIZE } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class FolderActionDeepSearch extends FolderAction {
    setup() {
        super.setup();
        this.label = _t("Search in Folder");
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        this.env.searchModel.deepSearchFolder(folder.id);
    }
}

export const folderActionDeepSearch = {
    Component: FolderActionDeepSearch,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(
            env,
            target,
            ({ documentService, folder }) =>
                documentService.userIsInternal && typeof folder.id === "number"
        ),
};
