import { STATIC_COG_GROUP_ACTION_ACCESS } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { _t } from "@web/core/l10n/translation";

export class DocumentsCogMenuItemDownload extends FolderAction {
    setup() {
        super.setup();
        this.label = _t("Download");
    }

    async doActionOnFolder(folder) {
        await this.action.doAction({
            type: "ir.actions.act_url",
            url: `/documents/content/${encodeURIComponent(folder.access_token)}`,
        });
    }
}

/** @type folderAction */
export const folderActionDownload = {
    Component: DocumentsCogMenuItemDownload,
    groupNumber: STATIC_COG_GROUP_ACTION_ACCESS,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.canDownload(folder)
        ),
};
