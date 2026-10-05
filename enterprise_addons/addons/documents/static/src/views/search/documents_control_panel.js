import { DocumentsAction } from "@documents/views/action/documents_action";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { DocumentsBreadcrumbs } from "@documents/components/documents_breadcrumbs";
import { DocumentsCogMenu } from "../cog_menu/documents_cog_menu";
import { onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DocumentsControlPanel extends ControlPanel {
    static template = "documents.ControlPanel";
    static components = {
        ...ControlPanel.components,
        DocumentsBreadcrumbs,
        DocumentsCogMenu,
        DocumentsAction,
    };

    setup() {
        super.setup();
        this.documentService = useService("document.document");

        onPatched(() => {
            const searchPanelContainer = document.querySelector(".o_search_panel");
            if (searchPanelContainer) {
                searchPanelContainer.classList.toggle(
                    "d-none",
                    this.uiService.isSmall && this.env.model.root.selection.length
                );
            }
        });
    }

    /**
     * Return the current folder ID.
     */
    get currentFolderId() {
        return this.env.searchModel.getSelectedFolderId();
    }

    get showActions() {
        if (this.env.searchModel.context.documents_view_secondary) {
            return false;
        }
        const previewing = !!this.documentService.state.previewedDocument;
        const focusing = !!this.documentService.state.focusedRecord;
        const focusedSelected =
            focusing &&
            !!this.env.model.root.selection.find(
                (r) => r.id === this.documentService.state.focusedRecord.id
            );
        return !previewing && (!focusing || focusedSelected);
    }

    get pathBreadcrumbs() {
        if (
            this.env.model.config.context.active_model || // Users come from another app
            this.env.model.config.context.documents_show_default_breadcrumb
        ) {
            return [
                ...this.env.config.breadcrumbs.slice(0, -1),
                {
                    name: this.env.searchModel.getSelectedFolder().display_name,
                },
            ];
        }

        return this.env.searchModel
            .getSelectedFolderAndParents()
            .reverse()
            .map((folder) => ({
                jsId: folder.id,
                name: folder.display_name,
                onSelected: () => {
                    const folderSection = this.env.searchModel.getSections()[0];
                    this.env.searchModel.toggleCategoryValue(folderSection.id, folder.id);
                },
            }));
    }

    switchView(viewType, newWindow) {
        if (this.uiService.isSmall && this.documentService.state.rightPanelVisible) {
            // Ensure chatter is reset on view change
            // to avoid needing another scrollIntoView
            this.documentService.toggleRightPanelVisibility();
        }
        if (this.env.config.switchView) {
            return this.env.config.switchView(viewType);
        }
        super.switchView(viewType, newWindow);
    }
}
