import { useSetupAction } from "@web/search/action_hook";
import { SearchModel } from "@web/search/search_model";
import { browser } from "@web/core/browser/browser";
import { router } from "@web/core/browser/router";
import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class DocumentsSearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        this.documentService = useService("document.document");
        this.orm = useService("orm");
        this.uiService = useService("ui");
        this.skipLoadClosePreview = false;
        this.deepSearchItemId = null;
        useSetupAction({
            beforeLeave: () => {
                this._updateRouteState({ folder_id: undefined });
            },
        });
    }

    async load(config) {
        if (this.documentService.initData.documentId || config.context.documents_init_document_id) {
            // Make sure target document is found (if accessible).
            config.irFilters.forEach((fil) => {
                fil.is_default = false;
            });
            for (const key in config.context) {
                // logic used in _extractSearchDefaultsFromGlobalContext, here to group with above
                const searchDefaultMatch = /^search_default_(.*)$/.exec(key);
                if (searchDefaultMatch) {
                    delete config.context[key];
                }
                if (key === "documents_init_document_id") {
                    this.documentService.documentIdToRestoreOnce =
                        config.context.documents_init_document_id;
                    delete config.context[key];
                }
            }
        }

        await super.load(config);
        if (this._isFetchSectionsRequired()) {
            await this._fetchSections(this.categories, this.filters);
        }

        if (this.getSelectedFolderId()) {
            let folderId = router.current.user_folder_id || this.getSelectedFolderId();
            const folderSection = this.getSections()[0];
            if (!folderSection.values.has(folderId)) {
                folderId = false;
            }
            this.toggleCategoryValue(folderSection.id, folderId);
        } else {
            this.documentService.currentFolderAccessToken = undefined;
        }
    }

    /**
     * Override to add rootId and pre-process user_folder_id.
     *
     * @override
     */
    _createCategoryTree(sectionId, result) {
        const category = this.sections.get(sectionId);
        // Clear non-permanent keys, necessary to 'forget' archived folders.
        for (const folderId of category.values.keys()) {
            if (typeof folderId === "number") {
                category.values.delete(folderId);
            }
        }
        // Match ids to construct tree
        for (const value of result.values) {
            if (!isNaN(value.user_folder_id)) {
                value.user_folder_id = Number(value.user_folder_id);
            }
        }
        super._createCategoryTree(...arguments);
        const findRootId = (folder) => {
            if (!folder.parentId) {
                return folder.id;
            }
            const parent = category.values.get(folder.parentId);
            if (!parent) {
                return false;
            }
            if (parent.rootId !== undefined) {
                return parent.rootId;
            } else {
                const rootId = findRootId(parent);
                parent.rootId = rootId;
                return rootId;
            }
        };
        for (const [, folder] of category.values) {
            if (!folder.rootId) {
                folder.rootId = findRootId(folder);
            }
        }
    }

    /**
     * @override
     */
    _extractSearchDefaultsFromGlobalContext() {
        const { searchDefaults, searchPanelDefaults } =
            super._extractSearchDefaultsFromGlobalContext(...arguments);
        if (searchPanelDefaults.user_folder_id) {
            if (!isNaN(searchPanelDefaults.user_folder_id)) {
                // Search panel keys (values) only support integers
                searchPanelDefaults.user_folder_id = Number(searchPanelDefaults.user_folder_id);
            }
            if (!this.globalContext.no_documents_unique_folder_id) {
                this.globalContext["documents_unique_folder_id"] =
                    searchPanelDefaults.user_folder_id;
            }
        }
        return { searchDefaults, searchPanelDefaults };
    }

    //---------------------------------------------------------------------
    // Actions / Getters
    //---------------------------------------------------------------------

    /**
     * Returns a description of each folder (record of documents.document, type === 'folder').
     * @returns {Object[]}
     */
    getFolders() {
        const { values } = this.getSections()[0];
        return [...values.values()];
    }

    /**
     * Returns the folder corresponding to the provided id, if any, false otherwise.
     * @returns {Object | false}
     */
    getFolderById(folderId) {
        const folderSection = this.getSections()[0];
        const folder = folderSection && folderSection.values.get(folderId);
        return folder || false;
    }

    /**
     * Returns the id of the current selected folder, if any, false
     * otherwise.
     * @returns {number | false}
     */
    getSelectedFolderId() {
        const { activeValueId } = this.getSections()[0];
        return activeValueId;
    }

    /**
     * Returns the current selected folder, if any, false otherwise.
     * @returns {Object | false}
     */
    getSelectedFolder() {
        const folderSection = this.getSections()[0];
        return this.getFolderById(folderSection.activeValueId);
    }

    /**
     * Returns the folder and all its parents, if any.
     * @returns {Object[]}
     */
    getFolderAndParents(folder) {
        const folders = [];
        const folderSection = this.getSections()[0];
        while (folder) {
            folders.push(folder);
            folder = folder.folder_id
                ? folderSection.values.get(folder.folder_id)
                : folderSection.values.get(folder.user_folder_id);
        }
        return folders;
    }

    /**
     * Returns the current selected folder and all its parents, if any.
     * @returns {Object[]}
     */
    getSelectedFolderAndParents() {
        const folderSection = this.getSections()[0];
        const folder = folderSection.values.get(folderSection.activeValueId || false);
        return this.getFolderAndParents(folder);
    }

    /**
     * Lazy load the tags.
     * @returns {Object[]}
     */
    async getTags() {
        if (this._tags) {
            return this._tags;
        }
        const result = await this.orm.call("documents.tag", "name_search", [], {});
        this._tags = result.map((tag) => ({ id: tag[0], name: tag[1] }));
        return this._tags;
    }

    /**
     * Overridden to write the new value in the local storage.
     * And to write the folder_id in the url.
     * @override
     * @param {number} sectionId
     * @param {number|false} valueId
     */
    toggleCategoryValue(sectionId, valueId) {
        const oldValueId = this.getSelectedFolderId();
        super.toggleCategoryValue(...arguments);
        const folderAndParents = this.getSelectedFolderAndParents();
        if (this.isDeepSearch && !folderAndParents.find((f) => f.id === oldValueId)) {
            this.toggleSearchItem(this.documentService.deepSearchItemId);
            this.documentService.state.shouldFocusSearchBar = false;
        } else {
            this.documentService.state.shouldFocusSearchBar = true;
        }
        const selectedFolder = folderAndParents[0];
        if (!this.context.documents_view_secondary) {
            browser.localStorage.setItem("searchpanel_documents_document", valueId);
            this.documentService.updateDocumentURL(selectedFolder);
        }
        if (typeof valueId === "number") {
            if (selectedFolder.childrenIds && selectedFolder.childrenIds.length) {
                this.documentService.logAccess(selectedFolder.access_token);
            } else {
                this.documentService.logAccess(selectedFolder.access_token).then((result) => {
                    if (result && result?.reload) {
                        this._reloadSearchModel(true);
                    }
                });
            }
        }
        if (!this.uiService.isSmall) {
            this.trigger("focus-search");
        }
    }

    /**
     * Add/modify search filters to search inside passed folder
     * @param {Number} folderId
     */
    deepSearchFolder(folderId) {
        this.toggleCategoryValue(this.getSections()[0].id, folderId);
        if (this._ensureDeepSearchItemId()) {
            this.toggleSearchItem(this.documentService.deepSearchItemId);
        }
        this.documentService.state.shouldFocusSearchBar = true;
    }

    /**
     * Updates the tag ids of a record matching the given value.
     * @param {number[]} recordIds
     * @param {number} valueId
     * @param {number} x2mCommand command (4 to add a tag, 3 to remove it)
     */
    async updateRecordTagId(recordIds, valueId, x2mCommand = 4) {
        await this.orm.write("documents.document", recordIds, {
            tag_ids: [[x2mCommand, valueId]],
        });
        this.skipLoadClosePreview = true;
        this.trigger("update");
    }

    //---------------------------------------------------------------------
    // Private
    //---------------------------------------------------------------------

    async _reloadSearchModel(reloadCategories) {
        // By default, categories are not reloaded.
        if (reloadCategories) {
            await this._reloadSearchPanel(true);
        }
        await this._notify();
    }

    async _reloadSearchPanel(skipUpdate = false) {
        await this._fetchSections(
            this.getSections((s) => s.type === "category"),
            []
        );
        if (!skipUpdate) {
            this.trigger("update-search-panel");
        }
    }

    /**
     * Optimize searches
     * @override
     */
    _getCategoryDomain() {
        const userFolderCategory = this.categories.find(
            (cat) => cat.fieldName === "user_folder_id"
        );
        if (["COMPANY", "MY", "RECENT"].includes(userFolderCategory.activeValueId)) {
            return [["user_folder_id", "=", userFolderCategory.activeValueId]];
        }
        if (userFolderCategory.activeValueId === "TRASH") {
            return [["active", "=", false]];
        }
        if (userFolderCategory.activeValueId === "SHARED") {
            return Domain.and([
                [["shortcut_document_id", "=", false]], // no need to show them, the target will be here (or nested)
                [["user_folder_id", "=", "SHARED"]],
            ]).toList();
        }
        if (!userFolderCategory.activeValueId) {
            if (this.context.documents_unique_folder_id) {
                const domain = [["folder_id", "child_of", this.context.documents_unique_folder_id]];
                const doc_domain = this.context.documents_linked_records_domain;
                if (doc_domain) {
                    return Domain.or([domain, doc_domain]);
                }
                return domain;
            }
            return [];
        }
        const folder = this.getSelectedFolder();
        const folderIdToOpen = folder?.shortcut_document_id?.length
            ? folder.shortcut_document_id[0]
            : userFolderCategory.activeValueId;
        const result = super._getCategoryDomain();
        const folderLeafIdx = result.findIndex(
            (leaf) => leaf[0] === "user_folder_id" && leaf[1] === "="
        );
        if (folderLeafIdx !== -1) {
            const domain = this.isDeepSearch
                ? ["&", ["folder_id", "child_of", folderIdToOpen], ["id", "!=", folderIdToOpen]]
                : [["folder_id", "=", folderIdToOpen]];
            result.splice(folderLeafIdx, 1, ...domain);
        }
        return result;
    }

    get isDeepSearch() {
        return (
            !!this.documentService.deepSearchItemId &&
            this.query.some((item) => item.searchItemId === this.documentService.deepSearchItemId)
        );
    }

    /**
     * @return {boolean} True if existed
     */
    _ensureDeepSearchItemId() {
        if (this.documentService.deepSearchItemId) {
            return true;
        }
        for (const searchItem of Object.values(this.searchItems)) {
            if (searchItem.name === "is_deep_search") {
                this.documentService.deepSearchItemId = searchItem.id;
                return true;
            }
        }
        // Fallback if not on the search view
        this.createNewFilters([
            {
                description: _t("All children"),
                domain: [],
                name: "is_deep_search",
            },
        ]);
        this.documentService.deepSearchItemId = this.nextId - 1;
        return false;
    }

    /**
     * @override Force specific ordering in RECENT and TRASH.
     */
    get orderBy() {
        if (this.sections.get(1).activeValueId === "TRASH") {
            return [
                { name: "create_date", asc: false },
                { name: "is_folder", asc: false },
            ];
        }
        if (this.sections.get(1).activeValueId === "RECENT") {
            return [
                { name: "is_folder", asc: true },
                { name: "last_access_date_group", asc: false },
                { name: "write_date", asc: false },
            ];
        }
        return super.orderBy;
    }

    get groupBy() {
        const groupBy = super.groupBy;
        if (!groupBy?.length && this.sections.get(1).activeValueId === "RECENT") {
            return ["last_access_date_group"];
        }
        return groupBy;
    }

    _isCategoryValueReachable(category, valueId) {
        const queue = [...category.rootIds];
        let folder;
        while ((folder = category.values.get(queue.pop()))) {
            if (folder.id === valueId) {
                return true;
            }
            queue.push(...folder.childrenIds);
        }
        return false;
    }

    /**
     * @override
     */
    _ensureCategoryValue(category, valueIds) {
        if (
            valueIds.includes(category.activeValueId) &&
            this._isCategoryValueReachable(category, category.activeValueId)
        ) {
            return;
        }
        if (
            !this.documentService.initData.folder_id &&
            this.context.documents_init_folder_id !== undefined
        ) {
            category.activeValueId = this.context.documents_init_folder_id || false;
            return;
        }
        // If not set in context, or set to an unknown value, set active value
        // from localStorage
        const storageItem = browser.localStorage.getItem("searchpanel_documents_document");
        category.activeValueId =
            storageItem && !["COMPANY", "MY", "RECENT", "SHARED", "TRASH"].includes(storageItem)
                ? JSON.parse(storageItem)
                : storageItem;
        if (
            ["COMPANY", "MY", "RECENT", "SHARED", "TRASH"].includes(category.activeValueId) ||
            (valueIds.includes(category.activeValueId) &&
                this._isCategoryValueReachable(category, category.activeValueId))
        ) {
            return;
        }
        // valueIds might contain different values than category.values
        if (category.values.has(category.activeValueId)) {
            // We might be in a deleted subfolder, try to find the parent.
            let newSection = category.values.get(
                category.values.get(category.activeValueId).parentId
            );
            while (newSection && !this._isCategoryValueReachable(category, newSection.id)) {
                newSection = category.values.get(newSection.parentId);
            }
            if (newSection) {
                category.activeValueId = newSection.id || valueIds[Number(valueIds.length > 1)];
            } else {
                category.activeValueId = this.documentService.userIsInternal
                    ? "COMPANY"
                    : valueIds[0];
            }
            browser.localStorage.setItem("searchpanel_documents_document", category.activeValueId);
        } else {
            // If still not a valid value, default to All (id=false)
            category.activeValueId = false;
        }
    }

    /**
     * @override
     */
    _shouldWaitForData() {
        return true;
    }

    _updateRouteState(state) {
        router.pushState(state);
    }

    _isFetchSectionsRequired() {
        return false;
    }

    /**
     * Knowledge embeddings dedicated methods, preventing leaking information.
     * Not in a bridge module as it should never be deactivated.
     */
    exportKnowledgeState() {
        const state = super.exportState(...arguments);
        const user_folder_id = this.getSelectedFolderId();
        if (!user_folder_id) {
            throw new Error(_t("Not allowed, select a folder")); // safety, shouldn't be possible
        }
        state.sections.forEach((section) => {
            section[1].values = [section[1].values[0]]; // Keep "All"
            section[1].activeValueId = false;
        });
        Object.assign(state.searchPanelInfo, { loaded: false, shouldReload: true });
        return state;
    }

    get knowledgeViewContext() {
        const folder = this.getSelectedFolder();
        const folderOrTarget = folder.shortcut_document_id
            ? { id: folder.shortcut_document_id[0], access_token: folder.target_access_token }
            : { id: folder.id, access_token: folder.access_token };
        return {
            documents_show_default_breadcrumb: true,
            documents_view_secondary: true,
            searchpanel_default_user_folder_id: folderOrTarget.id,
            documents_shared_access_token: folderOrTarget.access_token,
        };
    }
}
