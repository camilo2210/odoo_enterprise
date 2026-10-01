import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { FolderAction } from "./folder_action";
import { STATIC_COG_GROUP_ACTION_ORGANIZE } from "@documents/views/cog_menu/documents_cog_menu_group";

class DocumentsCogMenuItemOperation extends FolderAction {
    setup() {
        super.setup();
        this.operation = null;
        this.documentService = useService("document.document");
    }

    async doActionOnFolder(folder) {
        await this.documentService.openOperationDialog({
            documents: [
                {
                    id: folder.id,
                    name: folder.display_name,
                    shortcut_document_id: folder.shortcut_document_id,
                },
            ],
            operation: this.operation,
            onClose: () => this.reload(),
        });
    }
}

export class DocumentsCogMenuItemDuplicate extends DocumentsCogMenuItemOperation {
    setup() {
        super.setup();
        this.label = _t("Duplicate");
        this.operation = "copy";
    }
}

export class DocumentsCogMenuItemMove extends DocumentsCogMenuItemOperation {
    setup() {
        super.setup();
        this.label = _t("Move");
        this.operation = "move";
    }
}

export class DocumentsCogMenuItemShortcut extends DocumentsCogMenuItemOperation {
    setup() {
        super.setup();
        this.label = _t("Create Shortcut");
        this.operation = "shortcut";
    }
}

/** @type folderAction */
export const folderActionDuplicate = {
    Component: DocumentsCogMenuItemDuplicate,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.isEditable(folder)
        ),
};

/** @type folderAction */
export const folderActionMove = {
    Component: DocumentsCogMenuItemMove,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.isEditable(folder)
        ),
};

/** @type folderAction */
export const folderActionShortcut = {
    Component: DocumentsCogMenuItemShortcut,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(
            env,
            target,
            ({ folder, documentService }) =>
                documentService.isEditable(folder) && !folder.shortcut_document_id
        ),
};
