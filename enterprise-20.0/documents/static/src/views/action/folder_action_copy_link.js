import { STATIC_COG_GROUP_ACTION_ORGANIZE } from "@documents/views/cog_menu/documents_cog_menu_group";
import { FolderAction } from "./folder_action";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";

export class DocumentsCogMenuItemCopyLink extends FolderAction {
    setup() {
        super.setup();
        this.icon = "link";
        this.label = _t("Copy Link");
        this.notification = useService("notification");
    }

    async doActionOnFolder(folder) {
        const accessUrl = url(`/odoo/documents/${encodeURIComponent(folder.access_token)}`);
        await browser.navigator.clipboard.writeText(accessUrl);
        this.notification.add(_t("Link copied to clipboard!"), { type: "success" });
    }
}

/** @type folderAction */
export const folderActionCopyLink = {
    Component: DocumentsCogMenuItemCopyLink,
    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
    isDisplayed: (env, target) =>
        target &&
        FolderAction.isVisible(env, target, ({ folder, documentService }) =>
            documentService.isFolderSharable(folder)
        ),
};
