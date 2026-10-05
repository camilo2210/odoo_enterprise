import { STATIC_COG_GROUP_ACTION_PIN } from "./documents_cog_menu_group";
import { FolderAction } from "@documents/views/action/folder_action";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentsCogMenuItemAutomations extends FolderAction {
    setup() {
        super.setup();
        this.label = _t("Automations");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
    }

    async doActionOnFolder(folder) {
        this.env?.documentsView.bus.trigger("documents-open-automations", {
            folderId: folder.id,
            folderDisplayName: folder.display_name,
        });
    }
}

/** @type folderAction */
export const documentsCogMenuItemAutomations = {
    Component: DocumentsCogMenuItemAutomations,
    groupNumber: STATIC_COG_GROUP_ACTION_PIN,
    isDisplayed: (env, target) =>
        env.model.documentService.userIsDocumentUser &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.isEditable(folder)
        ),
};
