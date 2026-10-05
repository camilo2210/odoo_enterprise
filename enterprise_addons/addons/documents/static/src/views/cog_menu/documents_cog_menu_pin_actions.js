import { proxy } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
import { STATIC_COG_GROUP_ACTION_PIN } from "./documents_cog_menu_group";
import { FolderAction } from "@documents/views/action/folder_action";

export class DocumentsCogMenuPinAction extends FolderAction {
    static template = "documents.DocumentCogMenuPinAction";
    static components = { Dropdown };

    setup() {
        this.action = useService("action");
        this.documentService = useService("document.document");
        this.notification = useService("notification");

        this.documentsState = proxy({ actions: [], isLoading: true });
        this._reloadSearchModel = debounce(() => {
            this.env.searchModel._reloadSearchModel(true);
        }, 1500);

        const folderId = this.env.searchModel.getSelectedFolderId();
        this.documentService.getActions(folderId).then((actions) => {
            // Do not block `onWillStart` to not create a lag when opening the cogwheel
            this.documentsState.actions = actions;
            this.documentsState.isLoading = false;
        });
    }

    async onEnableAction(actionId) {
        const currentFolderId = this.env.searchModel.getSelectedFolderId();
        if (!currentFolderId || typeof currentFolderId !== "number") {
            this.notification.add(_t("You can not pin actions for that folder."), {
                type: "warning",
            });
            return;
        }

        // Toggle immediately the action to not create a lag (will be restored in "catch" if it fails)
        const action = this.documentsState.actions.find((a) => a.id === actionId);
        action.is_embedded = !action.is_embedded;
        try {
            await this.documentService.enableAction(currentFolderId, actionId);
        } catch {
            action.is_embedded = !action.is_embedded;
        }
        this._reloadSearchModel();
    }
}

/** @type folderAction */
export const documentsCogMenuPinAction = {
    Component: DocumentsCogMenuPinAction,
    groupNumber: STATIC_COG_GROUP_ACTION_PIN,
    isDisplayed: (env) =>
        env.model.documentService.userIsDocumentUser &&
        FolderAction.isVisible(env, undefined, ({ folder, documentService }) =>
            documentService.isEditable(folder)
        ),
};
