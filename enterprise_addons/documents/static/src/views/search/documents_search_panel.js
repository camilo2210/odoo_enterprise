import { render } from "@web/owl2/utils";
import { AccessRightsUpdateConfirmationDialog } from "@documents/owl/components/access_update_confirmation_dialog/access_update_confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { SearchPanel } from "@web/search/search_panel/search_panel";
import { useNestedSortable } from "@web/core/utils/nested_sortable";
import { usePopover } from "@web/core/popover/popover_hook";
import { useBus, useService } from "@web/core/utils/hooks";
import { utils as uiUtils } from "@web/core/ui/ui_utils";
import { onWillStart, proxy } from "@odoo/owl";
import { DocumentsSearchPanelActions } from "./documents_search_panel_actions";

const DND_ALLOWED_SPECIAL_DESTINATIONS = ["COMPANY", "MY"];

/**
 * This file defines the DocumentsSearchPanel component, an extension of the
 * SearchPanel to be used in the documents kanban/list views.
 */

export class DocumentsSearchPanel extends SearchPanel {
    static modelExtension = "DocumentsSearchPanel";
    static template = "documents.SearchPanel";
    static subTemplates = {
        section: "web.SearchPanel.Section",
        category: "documents.SearchPanel.Category",
        filtersGroup: "documents.SearchPanel.FiltersGroup",
    };
    static rootIcons = {
        false: ["folder", ""],
        COMPANY: ["business", "oi-filled"],
        MY: ["storage", ""],
        RECENT: ["schedule", ""],
        SHARED: ["group", "oi-filled"],
        TRASH: ["delete", "oi-filled"],
    };
    setup() {
        super.setup(...arguments);
        const { uploads } = useService("file_upload");
        this.documentService = useService("document.document");
        this.documentUploads = uploads;
        proxy(uploads);
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.action = useService("action");
        this.popover = usePopover(DocumentsSearchPanelActions, {
            onClose: () => this.anchor.remove(),
            popoverClass: "o_search_panel_folder_actions_popover dropdown-menu o-dropdown--menu",
            position: "bottom-start",
        });
        this.dialog = useService("dialog");

        onWillStart(async () => {
            await this.env.searchModel.sectionsPromise;
            if (this.env.model.config.context.active_model) {
                // Ensure folders in search panel are folded when users come from another app
                const categories = this.env.searchModel.getSections((s) => s.type === "category");
                for (const category of categories) {
                    this.state.expanded[category.id] = {};
                }
            } else {
                const selectedFolderId = await this.env.searchModel.getSelectedFolderId();
                if (selectedFolderId) {
                    this.state.expanded[this.sections[0].id]["COMPANY"] = true;
                    this._expandFolder({ folderId: selectedFolderId });
                }
            }
        });

        useBus(this.env.documentsView.bus, "documents-expand-folder", (ev) => {
            this._expandFolder(ev.detail);
        });

        useBus(this.env.searchModel, "update-search-panel", async () => {
            this.updateActiveValues();
            render(this);
        });

        useNestedSortable({
            ref: this.root,
            groups: ".o_search_panel_category",
            elements: "li:not(.o_all_or_trash_category)",
            enable: () => this.documentService.userIsInternal,
            nest: true,
            nestInterval: 10,
            /**
             * When the placeholder moves, unfold the new parent and show/hide carets
             * where needed.
             * @param {HTMLElement} parent - parent element of where the element was moved
             * @param {HTMLElement} newGroup - group in which the element was moved
             * @param {{parent: HTMLElement}} prevPos - element's parent before the move
             * @param {HTMLElement} placeholder - hint element showing the current position
             */
            onMove: ({ parent, newGroup, prevPos, placeholder }) => {
                if (parent) {
                    parent.classList.add("o_has_treeEntry");
                    placeholder.classList.add("o_treeEntry");
                    const parentSectionId = parseInt(newGroup.dataset.sectionId);
                    const parentValueId = parseInt(parent.dataset.valueId);
                    this.state.expanded[parentSectionId][parentValueId] = true;
                } else {
                    placeholder.classList.remove("o_treeEntry");
                }
                if (prevPos.parent && !prevPos.parent.querySelector("li")) {
                    prevPos.parent.classList.remove("o_has_treeEntry");
                }
            },
            onDrop: async ({ element, parent, next }) => {
                const draggingFolderId = parseInt(element.dataset.valueId);
                const draggingFolder = this.env.searchModel.getFolderById(draggingFolderId);
                const draggingFolderRootId = draggingFolder.rootId;
                let parentFolderId = parent ? parent.dataset.valueId : false;
                const beforeFolderId = next ? parseInt(next.dataset.valueId) : false;
                if (
                    draggingFolderId === parseInt(parentFolderId) ||
                    isNaN(draggingFolderId) ||
                    !parentFolderId ||
                    this._notifyWrongDropDestination(parentFolderId)
                ) {
                    return;
                }
                const parentFolderRootId =
                    this.env.searchModel.getFolderById(parentFolderId).rootId;
                if (
                    !this.documentService.userIsDocumentManager &&
                    (!parentFolderRootId || parentFolderRootId === "COMPANY")
                ) {
                    return;
                }
                if (parentFolderRootId === "MY" && draggingFolderRootId !== "MY") {
                    await this.orm.call(
                        "documents.document",
                        "action_create_shortcut",
                        [draggingFolderId],
                        { location_user_folder_id: parentFolderId.toString() }
                    );
                    return this.env.searchModel._reloadSearchModel(true);
                }
                if (!DND_ALLOWED_SPECIAL_DESTINATIONS.includes(parentFolderId)) {
                    parentFolderId = parseInt(parentFolderId);
                }
                const parentFolder = this.env.searchModel.getFolderById(parentFolderId);
                if (
                    !DND_ALLOWED_SPECIAL_DESTINATIONS.includes(parentFolderId) &&
                    (draggingFolder.access_internal !== parentFolder.access_internal ||
                        draggingFolder.access_via_link !== parentFolder.access_via_link ||
                        (parentFolder.access_via_link !== "none" &&
                            draggingFolder.is_access_via_link_hidden !==
                                parentFolder.is_access_via_link_hidden))
                ) {
                    this.dialog.add(AccessRightsUpdateConfirmationDialog, {
                        destinationFolder: parentFolder,
                        confirm: async () => {
                            await this.orm.call("documents.document", "action_move_folder", [
                                [draggingFolderId],
                                parentFolderId.toString() || false,
                                beforeFolderId,
                            ]);
                            await this.env.searchModel._reloadSearchModel(true);
                        },
                        cancel: () => {},
                    });
                    return;
                }
                await this.orm.call("documents.document", "action_move_folder", [
                    [draggingFolderId],
                    parentFolderId ? parentFolderId.toString() : false,
                    beforeFolderId,
                ]);
                await this.env.searchModel._reloadSearchModel(true);
            },
        });
    }

    openActionsPopover(ev, section, value) {
        if (
            typeof value.id !== "number" ||
            uiUtils.isSmall() ||
            this.env.searchModel.context.documents_view_secondary
        ) {
            return;
        }
        const folder = this.env.searchModel.getFolderById(value.id);
        this.anchor = document.createElement("div");
        if (ev.type === "contextmenu") {
            this.anchor.style.cssText = `position:fixed;width:0;height:0;top:${ev.clientY}px;left:${ev.clientX}px;`;
        } else {
            const rect = (ev.currentTarget || ev.target).getBoundingClientRect();
            this.anchor.style.cssText = `position:fixed;width:0;height:0;top:${rect.bottom}px;left:${rect.left}px;`;
        }
        document.body.appendChild(this.anchor);
        this.popover.open(this.anchor, { env: this.env, folder });
    }

    isUploadingInFolder(folderId) {
        return Object.values(this.documentUploads).find(
            (upload) => upload.data.get("folder_id") === folderId
        );
    }

    //---------------------------------------------------------------------
    // Selection
    //---------------------------------------------------------------------

    /**
     * @param {Object} category
     * @param {Object} value
     */
    async toggleCategory(category, value) {
        if (category.activeValueId !== value.id) {
            const folder = this.env.searchModel.getFolderById(value.id);
            const isShortcut = !!folder.shortcut_document_id?.length;
            if (isShortcut && !this.env.searchModel.getFolderById(folder.shortcut_document_id[0])) {
                // Unknown folders are in the Trash.
                return this.env.searchModel.toggleCategoryValue(category.id, "TRASH");
            }
            this.env.searchModel.toggleCategoryValue(category.id, value.id);
        }
    }

    /**
     * @param {*} category
     * @param {*} value
     */
    async toggleFold(category, value) {
        if (value.childrenIds.length) {
            const categoryState = this.state.expanded[category.id];
            categoryState[value.id] = !categoryState[value.id];
        } else {
            this.getDropdownState(category.id).close();
        }
    }

    onFoldKeyDown(ev, category, value) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.toggleFold(category, value);
        }
    }

    _expandFolder({ folderId }) {
        let needRefresh = false;
        const sectionId = this.sections[0].id;
        const folders = this.env.searchModel.getFolderAndParents(
            this.env.searchModel.getFolderById(folderId)
        );
        if (folders[0].id === "COMPANY" || this.state.expanded[sectionId][folders[0].rootId]) {
            for (const folder of folders) {
                if (!this.state.expanded[sectionId][folder.id]) {
                    this.state.expanded[sectionId][folder.id] = true;
                    needRefresh = true;
                }
            }
        }
        if (needRefresh) {
            render(this, true);
        }
    }

    _notifyWrongDropDestination(folderId) {
        if (isNaN(folderId) && !DND_ALLOWED_SPECIAL_DESTINATIONS.includes(folderId)) {
            this.notification.add(
                _t("You can't create shortcuts in or move documents to this special folder."),
                {
                    title: _t("Invalid operation"),
                    type: "warning",
                }
            );
            return true;
        }
    }
}
