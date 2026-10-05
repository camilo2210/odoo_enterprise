import { PdfManager } from "@documents/owl/components/pdf_manager/pdf_manager";
import {
    STATIC_COG_GROUP_ACTION_BASE,
    STATIC_COG_GROUP_ACTION_DESTRUCTIVE,
    STATIC_COG_GROUP_ACTION_NATIVE,
    STATIC_COG_GROUP_ACTION_ORGANIZE,
    STATIC_COG_GROUP_ACTION_PIN,
    STATIC_COG_GROUP_ACTION_SECURITY,
    STATIC_COG_GROUP_ACTION_VERSION,
} from "@documents/views/cog_menu/documents_cog_menu_group";
import { getCommonEmbeddedActions } from "@documents/views/utils";
import {
    computed,
    EventBus,
    markup,
    onMounted,
    onWillUnmount,
    signal,
    t,
    useEffect,
    usePlugin,
    useProps,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ORM } from "@web/core/orm_plugin";
import { user } from "@web/core/user";
import { useBus, useService } from "@web/core/utils/hooks";
import { htmlJoin } from "@web/core/utils/html";
import { omit } from "@web/core/utils/objects";
import { makeActiveField } from "@web/model/relational_model/utils";
import { useSubEnv } from "@web/owl2/utils";
import { useSetupAction } from "@web/search/action_hook";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { PromoteStudioAutomationDialog } from "@web_enterprise/webclient/promote_studio/promote_studio_dialog";

/**
 * @typedef {import("@web/model/relational_model/record").Record} RelationalRecord
 */

/**
 * @param {RelationalRecord} rec
 */
function getRecordAttachment(rec) {
    const target = rec.shortcutTarget;
    return {
        // A negative ID prevents a reload from resolving to a real record, ensuring that the document name
        // is always shown instead of the potentially non renamed attachment name.
        id: -target.resId,
        name: target.data.name,
        mimetype: target.data.mimetype,
        url: target.data.url,
        documentId: target.resId,
        documentData: target.data,
    };
}

/**
 * @param {import("@odoo/owl").Signal<HTMLElement} ref
 */
function useWaitFor(ref) {
    function cleanup() {
        observer?.disconnect();
        clearTimeout(timeoutHandle);
    }

    /** @type {MutationObserver} */
    let observer;
    let timeoutHandle = 0;

    onWillUnmount(cleanup);

    /**
     * Waits for a given selector to be found inside a given root element within the
     * given time frame. It returns the element if found or null.
     *
     * @param {string} selector
     * @param {number} [timeout]
     */
    return async function waitFor(selector, timeout = 500) {
        const rootElement = ref();
        const initialEl = rootElement.querySelector(selector);
        if (initialEl) {
            return initialEl;
        }
        cleanup();
        /** @type {PromiseWithResolvers<Element | null} */
        const { promise, resolve } = Promise.withResolvers();
        observer = new MutationObserver(function runCheck() {
            const el = ref().querySelector(selector);
            if (el) {
                cleanup();
                resolve(el);
            }
        });
        observer.observe(rootElement, {
            childList: true,
            subtree: true,
        });
        timeoutHandle = setTimeout(() => {
            observer.disconnect();
            resolve(null);
        }, timeout);
        return promise;
    };
}

/**
 * @template {typeof import("@odoo/owl").Component} T
 * @param {T} ControllerComponent
 */
export const DocumentsControllerMixin = (ControllerComponent) =>
    class extends ControllerComponent {
        rootRef = signal.ref();
        previewStore = signal({});
        // Passed down to the view's <SearchBar inputRef="this.searchInputRef"/> (see
        // SearchBar.inputRef) so it can be focused from here without reaching into its DOM.
        searchInputRef = signal.ref();

        get hasSelectedRecords() {
            return this.targetRecords.length;
        }

        get modelParams() {
            const modelParams = super.modelParams;
            // activeFields for DocumentsDetailsPanel
            const { activeFields } = modelParams.config;
            for (const fieldName of DETAIL_PANEL_REQUIRED_FIELDS) {
                if (!(fieldName in activeFields)) {
                    activeFields[fieldName] = makeActiveField();
                }
            }
            if (!("res_id" in activeFields)) {
                activeFields.res_id = makeActiveField();
                activeFields.res_id.related = {
                    fields: {
                        display_name: {
                            name: "display_name",
                            type: "char",
                        },
                    },
                    activeFields: {
                        display_name: makeActiveField(),
                    },
                };
            }
            if (!("tag_ids" in activeFields)) {
                activeFields.tag_ids = makeActiveField();
                activeFields.tag_ids.related = {
                    activeFields: {
                        display_name: makeActiveField({ readonly: true }),
                        color: makeActiveField(),
                    },
                    fields: {
                        display_name: {
                            name: "display_name",
                            type: "char",
                            readonly: true,
                        },
                        color: {
                            name: "color",
                            type: "integer",
                            readonly: false,
                        },
                    },
                };
            }
            if (!("alias_tag_ids" in activeFields)) {
                activeFields.alias_tag_ids = { ...activeFields.tag_ids };
            }
            return modelParams;
        }

        /** @type {import("@documents/views/search/documents_search_model").DocumentsSearchModel} */
        get searchModel() {
            return this.env.searchModel;
        }

        get showActions() {
            const previewing = !!this.documentService.state.previewedDocument;
            const focusing = !!this.documentService.state.focusedRecord;
            const focusedSelected =
                focusing &&
                !!this.targetRecords.find(
                    (r) => r.id === this.documentService.state.focusedRecord.id
                );
            return !previewing && (!focusing || focusedSelected);
        }

        /** @type {RelationalRecord[]} */
        get targetRecords() {
            return this.model.targetRecords;
        }

        waitFor = useWaitFor(this.rootRef);

        setup() {
            // Ask only for the props we need here rather than reaching into the
            // component's full (read-only) props object.
            const { globalState } = useProps({
                globalState: t.any().optional(),
            });
            // The root selection is shared between views to keep the selection when
            // switching view: it is carried over through `globalState`. Expose it via
            // the env so the model can restore it (Owl 3 props are read-only, so it can
            // no longer be written back into `props.state`).
            useSubEnv({
                documentsView: {
                    bus: new EventBus(),
                    sharedSelection: globalState?.sharedSelection,
                },
            });

            super.setup();

            this.actionService = useService("action");
            this.dialogService = useService("dialog");
            this.documentService = useService("document.document");
            this.fileUploadService = useService("file_upload");
            this.notificationService = useService("notification");
            this.orm = usePlugin(ORM);
            this.store = useService("mail.store");
            this.uiService = useService("ui");

            // Shorthands to documents service properties/methods
            this.canUploadInFolder = this.documentService.canUploadInFolder.bind(
                this.documentService
            );
            this.firstLoadSelectId = this.documentService.initData?.documentId;
            this.userIsInternal = this.documentService.userIsInternal;
            this.userIsDocumentManager = this.documentService.userIsDocumentManager;

            this.searchBarToggler = useSearchBarToggler();
            useSubEnv({
                model: this.model,
                searchBarToggler: this.searchBarToggler,
            });

            this.onClickAddFolder = this.onClickAddFolder.bind(this);
            this.onClickDocumentsAddUrl = this.onClickDocumentsAddUrl.bind(this);
            this.onClickDocumentsRequest = this.onClickDocumentsRequest.bind(this);

            const selectionActions = {
                getMenuProps: computed(() => this.actionMenuProps),
                getTopBarActions: this.getTopBarActionMenuItems.bind(this),
            };
            onMounted(() => {
                this.documentService.registerSelectionActions(selectionActions);
                if (!this.searchModel.context.documents_view_secondary) {
                    this.documentService.updateDocumentURLRefresh();
                }
            });
            onWillUnmount(() => {
                this.documentService.unregisterSelectionActions(selectionActions);
            });

            // Keep selection between views
            useSetupAction({
                rootRef: this.rootRef,
                getGlobalState: () => ({
                    sharedSelection: this.model.exportSelection(),
                }),
            });

            const documentsViewBus = this.env.documentsView.bus;
            useBus(documentsViewBus, "documents-open-automations", (ev) =>
                this._openAutomations(ev.detail)
            );
            useBus(documentsViewBus, "documents-open-preview", (ev) =>
                this.onOpenDocumentsPreview(ev.detail)
            );
            useBus(documentsViewBus, "documents-close-preview", () => {
                this.documentService.setPreviewedDocument(null);
                this.documentService.documentList?.onDeleteCallback();
            });
            useBus(documentsViewBus, "documents-upload-files", (ev) =>
                this.uploadFiles({
                    ...ev.detail,
                    context: {
                        ...this.props.context,
                        ...ev.detail.context,
                    },
                })
            );

            useBus(this.documentService.bus, "DOCUMENT_RELOAD", () =>
                this.searchModel._reloadSearchModel(true)
            );

            // The search bar can be momentarily unmounted (e.g. hidden while a record is
            // selected, such as during a right-click), so `documentService.state.shouldFocusSearchBar`
            // may still be set once it remounts.
            useEffect(() => {
                const input = this.searchInputRef();
                if (input && this.documentService.state.shouldFocusSearchBar) {
                    this.documentService.state.shouldFocusSearchBar = false;
                    input.focus();
                }
            });

            useBus(
                this.fileUploadService.bus,
                "FILE_UPLOAD_ERROR",
                this._onFileUploadError.bind(this)
            );
            useBus(
                this.fileUploadService.bus,
                "FILE_UPLOAD_LOADED",
                this._onFileUploadLoaded.bind(this)
            );
        }

        /**
         * @returns {HTMLElement[]}
         */
        getSelectedDocumentsElements() {
            return [];
        }

        /**
         * @param {any} record
         * @returns {boolean}
         */
        isRecordPreviewable(record) {
            return record.isViewable();
        }

        /**
         * Open document preview when the view is loaded for a specific document such as in:
         *  * Direct access to the app via a document URL / _get_access_action
         *  * In-app redirection from shortcut
         */
        openInitialPreview() {
            if (!this.firstLoadSelectId) {
                return;
            }
            const initData = this.documentService.initData;
            const doc = this.model.root.records.find(
                (record) => record.data.id === this.firstLoadSelectId
            );
            if (doc) {
                this.firstLoadSelectId = false;
                doc.selected = true;
                if (initData.openPreview) {
                    initData.openPreview = false;
                    doc.onClickPreview(new Event("click"));
                }
            }
        }

        openTrashIfNecessary() {
            if (this.documentService.archivedDocumentRestored) {
                if (this.searchModel.getSelectedFolderId() !== "TRASH") {
                    const [section] = this.searchModel.getSections();
                    this.searchModel.toggleCategoryValue(section.id, "TRASH");
                }
                this.documentService.updateDocumentURL(undefined, [
                    { data: this.documentService.archivedDocumentRestored },
                ]);
                this.documentService.archivedDocumentRestored = undefined;
            }
        }

        async embeddedAction(documentIds, actionId, preventReload = false) {
            const context = {
                active_model: "documents.document",
                active_ids: documentIds,
            };
            const result = await this.orm.call(
                "documents.document",
                "action_execute_embedded_action",
                [actionId],
                { context }
            );

            if (result && typeof result === "object") {
                if (Object.hasOwn(result, "warning")) {
                    this.notificationService.add(
                        markup`<ul>${htmlJoin(
                            result["warning"]["documents"].map((d) => markup`<li>${d}</li>`)
                        )}</ul>`,
                        {
                            title: result["warning"]["title"],
                            type: "danger",
                        }
                    );
                    if (!preventReload) {
                        await this.model.load();
                    }
                } else if (!preventReload) {
                    await this.actionService.doAction(result, {
                        onClose: () => this.model.load(),
                    });
                    return;
                }
            } else if (!preventReload) {
                await this.model.load();
            }
        }

        getTopBarActionMenuItems() {
            const embeddedActions = Object.fromEntries(
                getCommonEmbeddedActions(this.targetRecords).map((embeddedAction) => [
                    embeddedAction.id,
                    {
                        description: embeddedAction.name,
                        sequence: 35,
                        callback: () => this.model.onDoAction(embeddedAction.id),
                        groupNumber: STATIC_COG_GROUP_ACTION_PIN,
                    },
                ])
            );
            embeddedActions.download = {
                isAvailable: () => this.targetRecords.some((r) => !r.isRequest()),
                sequence: 10,
                description: _t("Download"),
                callback: () => this.model.onDownload(),
                groupNumber: STATIC_COG_GROUP_ACTION_BASE,
            };
            embeddedActions.share = {
                isAvailable: () => this.userIsInternal && this.targetRecords.length > 0,
                sequence: 20,
                description: _t("Share"),
                icon: "share",
                callback: () => this.model.onShare(),
                groupNumber: STATIC_COG_GROUP_ACTION_BASE,
            };
            return embeddedActions;
        }

        getStaticActionMenuItems() {
            const selectionCount = this.targetRecords.length;
            const singleSelection = selectionCount === 1 && this.targetRecords[0];
            const isInTrash = this.searchModel.getSelectedFolderId() === "TRASH";
            const editMode = this.targetRecords.every((r) => r.data.user_permission === "edit");
            const allFavorited = this.targetRecords.every((r) => r.data.is_favorited);
            const someActive = this.targetRecords.some((r) => r.data.active);
            const someArchived = this.targetRecords.some((r) => !r.data.active);
            const someUnlocked = this.targetRecords.some((r) => !r.data.lock_uid);
            const menuItems = super.getStaticActionMenuItems?.() || {};
            if (menuItems.export) {
                // No export in activity view
                menuItems.export.iconClass = "invisible";
                menuItems.export.sequence = 120;
                menuItems.export.groupNumber = STATIC_COG_GROUP_ACTION_NATIVE;
            }
            const topBarActions = this.uiService.isSmall ? this.getTopBarActionMenuItems() : {};
            return {
                ...omit(menuItems, "archive", "delete", "duplicate", "unarchive"),
                ...topBarActions,
                rename: {
                    isAvailable: () => editMode && singleSelection && someUnlocked && !isInTrash,
                    sequence: 40,
                    description: _t("Rename"),
                    icon: "edit",
                    iconClass: "invisible",
                    callback: () => this.model.onRename(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },
                move: {
                    isAvailable: () => this.model.canMoveRecords,
                    sequence: 50,
                    description: _t("Move"),
                    icon: "login",
                    iconClass: "invisible",
                    callback: () => this.model.onMove(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },

                duplicate: {
                    isAvailable: () => this.model.canDuplicateRecords,
                    sequence: 60,
                    description: _t("Duplicate"),
                    icon: "content_copy",
                    iconClass: "invisible",
                    callback: () => this.model.onDuplicate(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },
                star: {
                    isAvailable: () =>
                        this.userIsInternal && selectionCount && editMode && !isInTrash,
                    sequence: 70,
                    description: allFavorited ? _t("Remove star") : _t("Add star"),
                    icon: "star",
                    iconClass: allFavorited ? "oi-filled" : "",
                    callback: () => this.model.onToggleFavorited(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },
                shortcut: {
                    isAvailable: () => this.userIsInternal && !isInTrash,
                    sequence: 80,
                    description: _t("Create Shortcut"),
                    icon: "open_in_new",
                    iconClass: "invisible",
                    callback: () => this.model.onCreateShortcut(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },
                copy: {
                    isAvailable: () => selectionCount && !isInTrash,
                    sequence: 90,
                    description: _t("Copy Links"),
                    icon: "link",
                    callback: () => this.model.onCopyLinks(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },
                deepSearch: {
                    isAvailable: () =>
                        this.userIsInternal &&
                        singleSelection &&
                        someActive &&
                        singleSelection.data.type === "folder",
                    sequence: 100,
                    description: _t("Search in Folder"),
                    icon: "search",
                    iconClass: "invisible",
                    callback: () => this.model.onDeepSearch(),
                    groupNumber: STATIC_COG_GROUP_ACTION_ORGANIZE,
                },
                // "Insert in spreadsheet" / "Export"
                pdf: {
                    isAvailable: () =>
                        this.userIsInternal &&
                        selectionCount &&
                        editMode &&
                        this.targetRecords.every(
                            (record) => record.isPdf() && !record.data.lock_uid
                        ) &&
                        !isInTrash,
                    sequence: 130,
                    description: singleSelection ? _t("Split PDF") : _t("Merge PDFs"),
                    icon: "merge",
                    iconClass: "invisible",
                    callback: () => this.model.onSplitPDF(),
                    groupNumber: STATIC_COG_GROUP_ACTION_NATIVE,
                },

                version: {
                    isAvailable: () => this.model.canManageVersions,
                    sequence: 140,
                    description: _t("Manage Versions"),
                    icon: "history",
                    iconClass: "invisible",
                    callback: () => this.model.onManageVersions(),
                    groupNumber: STATIC_COG_GROUP_ACTION_VERSION,
                },

                lock: {
                    isAvailable: () =>
                        this.userIsInternal &&
                        singleSelection &&
                        singleSelection.data.type !== "folder" &&
                        !isInTrash &&
                        editMode,
                    sequence: 150,
                    description: singleSelection?.data?.lock_uid ? _t("Unlock") : _t("Lock"),
                    icon: "lock",
                    iconClass: "invisible",
                    callback: () => this.model.onToggleLock(),
                    groupNumber: STATIC_COG_GROUP_ACTION_SECURITY,
                },

                trash: {
                    isAvailable: () =>
                        this.userIsInternal && editMode && someActive && someUnlocked,
                    sequence: 160,
                    description: _t("Trash"),
                    icon: "delete",
                    iconClass: "oi-filled",
                    callback: () => this.model.onArchive(),
                    groupNumber: STATIC_COG_GROUP_ACTION_DESTRUCTIVE,
                },
                restore: {
                    isAvailable: () => someArchived,
                    sequence: 170,
                    description: _t("Restore"),
                    icon: "history",
                    callback: () => this.model.onRestore(),
                    groupNumber: STATIC_COG_GROUP_ACTION_DESTRUCTIVE,
                },
                delete: {
                    isAvailable: () => this.model.canDeleteRecords,
                    sequence: 180,
                    description: _t("Delete"),
                    icon: "delete",
                    iconClass: "oi-filled",
                    callback: () => this.model.onDelete(),
                    groupNumber: STATIC_COG_GROUP_ACTION_DESTRUCTIVE,
                },
            };
        }

        hasShareDocuments() {
            const folder = this.searchModel.getSelectedFolder();
            const selectedRecords = this.model.root.selection.length;
            return typeof folder.id !== "number" && !selectedRecords;
        }

        /**
         * Updates the record currently focused in the right panel.
         * ensure that when the page is turned, the focus resets to the
         * currently open folder
         */
        onPageChange() {
            super.onPageChange();
            if (!this.env.searchModel.context.documents_view_secondary) {
                this.documentService.focusRecord(this.model.getContainerRecord());
            }
        }

        onClickAddFolder() {
            const currentFolder = this.searchModel.getSelectedFolderId();
            this.actionService.doAction("documents.action_folder_form", {
                additionalContext: {
                    default_type: "folder",
                    default_user_folder_id: currentFolder ? currentFolder.toString() : "MY", // false for "All"
                    ...(currentFolder === "COMPANY" ? { default_access_internal: "edit" } : {}),
                },
                fullscreen: this.uiService.isSmall,
                onClose: async () => {
                    await this.searchModel._reloadSearchModel(true);
                    this.env.documentsView.bus.trigger("documents-expand-folder", {
                        folderId: [false, "COMPANY"].includes(currentFolder) ? "MY" : currentFolder,
                    });
                },
            });
        }

        onClickDocumentsAddUrl() {
            const folderId = this.searchModel.getSelectedFolderId();
            this.actionService.doAction("documents.action_url_form", {
                additionalContext: {
                    default_type: "url",
                    default_partner_id: this.props.context.default_partner_id || false,
                    default_folder_id: this.searchModel.getSelectedFolderId(),
                    default_res_id: this.props.context.default_res_id || false,
                    default_res_model: this.props.context.default_res_model || false,
                    ...(folderId === "COMPANY" ? { default_owner_id: false } : {}),
                },
                fullscreen: this.uiService.isSmall,
                onClose: async () => {
                    await this.model.load();
                    this.model.notify();
                },
            });
        }

        onClickDocumentsRequest() {
            this.actionService.doAction("documents.action_request_form", {
                additionalContext: {
                    default_partner_id: this.props.context.default_partner_id || false,
                    default_folder_id:
                        this.searchModel.getSelectedFolderId() ||
                        this.searchModel.getFolders()[1].id,
                    default_res_id: this.props.context.default_res_id || false,
                    default_res_model: this.props.context.default_res_model || false,
                    default_requestee_id: this.props.context.default_partner_id || false,
                },
                fullscreen: this.uiService.isSmall,
                onClose: async () => {
                    await this.model.load();
                    this.model.notify();
                },
            });
        }

        /**
         * @param {Event & { currentTarget: HTMLInputElement }} ev
         */
        async onFileInputChange({ currentTarget }) {
            if (!currentTarget.files.length) {
                return;
            }
            await this.uploadFiles({
                files: currentTarget.files,
                accessToken: this.documentService.currentFolderAccessToken,
                context: this.props.context,
            });
            currentTarget.value = "";
        }

        onOpenDocumentsPreview({
            documents,
            embeddedActions,
            hasPdfSplit,
            isPdfSplit,
            mainDocument,
        }) {
            if (isPdfSplit) {
                this.previewStore.set({}); // Close preview
                return this._openPdfSplitter(documents, embeddedActions);
            }

            const documentsRecords = (
                (documents.length === 1 && this.model.root.records) ||
                documents
            )
                .filter((rec) => this.isRecordPreviewable(rec))
                .map((rec) =>
                    this.store.Document.insert({
                        id: rec.resId,
                        attachment: getRecordAttachment(rec),
                        name: rec.data.name,
                        mimetype: rec.data.mimetype,
                        url: rec.data.url,
                        displayName: rec.data.display_name,
                        record: rec,
                    })
                );
            // If there is a scrollbar we don't want it whenever the previewer is opened
            const docView = this.rootRef()?.querySelector(".o_documents_view");
            if (docView) {
                docView.classList.add("overflow-hidden");
            }
            const selectedResId = (mainDocument || documents[0]).resId;
            const selectedDocument = documentsRecords.find((rec) => rec.id === selectedResId);

            this.documentService.documentList = {
                documents: documentsRecords || [],
                folderId: this.searchModel.getSelectedFolderId(),
                initialRecordSelectionLength: documents.length,
                isSecondary: this.searchModel.context.documents_view_secondary,
                pdfManagerOpenCallback: (documents) =>
                    this._openPdfSplitter(documents, embeddedActions),
                onDeleteCallback: () => {
                    // We want to focus on the first selected document's element
                    const elements = this.getSelectedDocumentsElements();
                    if (elements.length) {
                        elements[0].focus();
                        if (!this.documentService.documentList.isSecondary) {
                            const focusedDocument =
                                this.documentService.documentList.documents.find(
                                    (d) => d.record.id === elements[0].dataset.id
                                );
                            this.documentService.focusRecord(focusedDocument?.record || null);
                        }
                    }
                    const docView = this.rootRef()?.querySelector(".o_documents_view");
                    if (docView) {
                        docView.classList.remove("overflow-hidden");
                    }

                    this.previewStore.set({});
                },
                hasPdfSplit,
                selectedDocument,
            };
            this.documentService.setPreviewedDocument(selectedDocument);

            this.previewStore.set({
                attachments: documentsRecords.map((doc) => doc.attachment),
                startIndex: documentsRecords.indexOf(selectedDocument),
            });
        }

        /**
         * Create several new documents inside a given folder (folder accessToken) or replace
         * the document's attachment by the given single file (binary accessToken).
         */
        async uploadFiles({ files, accessToken, context }) {
            const selectedUserFolderId =
                this.searchModel.getSelectedFolderId() ||
                context.documents_unique_folder_id ||
                "MY"; // False='ALL'
            if (!accessToken) {
                if (["COMPANY", "MY"].includes(selectedUserFolderId)) {
                    context.default_user_folder_id = selectedUserFolderId;
                } else {
                    accessToken =
                        this.searchModel.getFolderById(selectedUserFolderId)?.access_token;
                }
            }
            await this.documentService.uploadDocument(files, accessToken, context);
        }

        /**
         * @private
         * @param {any} result
         */
        _handleUploadError(result) {
            this.notificationService.add(result.error, {
                type: "danger",
                sticky: true,
            });
        }

        /**
         * @private
         * @param {CustomEvent<{ upload: { state?: string } }>} ev
         */
        _onFileUploadError(ev) {
            const { upload } = ev.detail;
            if (upload.state === "error") {
                this._handleUploadError({
                    error: _t("An error occurred while uploading."),
                });
            }
        }

        /**
         * @private
         * @param {CustomEvent<{ upload: { xhr: XMLHttpRequest } }>} ev
         */
        async _onFileUploadLoaded(ev) {
            const { xhr } = ev.detail.upload;
            if (xhr.status !== 200) {
                this._handleUploadError({
                    error: _t("status code: %(status)s, message: %(message)s", {
                        status: xhr.status,
                        message: xhr.response,
                    }),
                });
                return;
            }
            // Depending on the controller called, the response is different:
            // /documents/upload/xx: returns an array of document ids
            // /mail/attachment/upload: returns an object { "ir.attachment": ... }
            const newDocumentIds = JSON.parse(xhr.response);
            await this.model.load(this.props);
            this.model.notify();

            if (!Array.isArray(newDocumentIds)) {
                return;
            }

            const firstNewRecord = this.model.root.records.find((r) =>
                newDocumentIds.includes(r.resId)
            );
            if (!firstNewRecord) {
                return;
            }

            // need to change the selection one by one to have the right selection
            // otherwise the web client show the wrong selection
            await Promise.all(
                this.model.root.records.map((r) =>
                    r.toggleSelection(newDocumentIds.includes(r.resId))
                )
            );

            this.documentService.focusRecord(firstNewRecord, true);

            // Wait the record to be rendered and then focus it and scroll to it.
            const viewType = this.actionService.currentController?.view?.type;
            let recordElement;
            if (["kanban", "list"].includes(viewType)) {
                recordElement = await this.waitFor(
                    viewType === "kanban"
                        ? `.o_kanban_record[data-value-id="${firstNewRecord.resId}"]`
                        : `.o_data_row[data-value-id="${firstNewRecord.resId}"]`
                );
            }

            recordElement?.scrollIntoView?.({
                behavior: "instant",
                block: viewType === "kanban" ? "start" : "center",
            });
        }

        /**
         * Open Automation rules
         *
         * @private
         * @param {{
         *  folderId: number;
         *  folderDisplayName: string;
         * }} params
         */
        async _openAutomations({ folderId, folderDisplayName }) {
            const checkBaseAutomation = await this.orm.searchCount("ir.module.module", [
                ["name", "=", "base_automation"],
                ["state", "=", "installed"],
            ]);
            if (!checkBaseAutomation > 0) {
                return this.dialogService.add(PromoteStudioAutomationDialog, {
                    title: _t("Odoo Studio - Customize workflows in minutes"),
                });
            }
            const userHasAccessRight = await user.checkAccessRight("base.automation", "create");
            if (!userHasAccessRight) {
                return this.notificationService.add(
                    _t("Contact your Administrator to get access if needed."),
                    {
                        title: _t("Access to Automations"),
                        type: "info",
                    }
                );
            }
            const documentsModelId = await this.orm.search(
                "ir.model",
                [["model", "=", "documents.document"]],
                { limit: 1 }
            );
            return await this.actionService.doAction("base_automation.base_automation_act", {
                additionalContext: {
                    active_test: false,
                    default_model_id: documentsModelId[0],
                    search_default_model_id: documentsModelId[0],
                    default_name: _t("Put in %s", folderDisplayName),
                    default_filter_domain: [["folder_id", "in", [folderId]]],
                    default_trigger: "on_create_or_write",
                },
            });
        }

        /**
         * @private
         * @param {RelationalRecord[]} documents
         * @param {any} embeddedActions
         */
        _openPdfSplitter(documents, embeddedActions) {
            let newDocumentIds = [];
            let forceDelete = false;
            this.dialogService.add(
                PdfManager,
                {
                    documents: documents.map((doc) => doc.data),
                    embeddedActions,
                    onProcessDocuments: async ({
                        documentIds,
                        actionId,
                        exit,
                        isForcingDelete,
                    }) => {
                        forceDelete = isForcingDelete;
                        if (documentIds?.length) {
                            newDocumentIds = [...new Set(newDocumentIds.concat(documentIds))];
                        }
                        if (actionId) {
                            await this.embeddedAction(documentIds, actionId, !exit);
                        }
                    },
                },
                {
                    onClose: async () => {
                        if (!newDocumentIds.length && !forceDelete) {
                            return;
                        }
                        await this.model.load();
                        await this.model.root.deleteRecords(
                            documents.filter((record) => !newDocumentIds.includes(record.resId))
                        );
                        await Promise.all(
                            this.model.root.records
                                .filter((r) => newDocumentIds.includes(r.resId))
                                .map((r) => r.toggleSelection(true))
                        );
                    },
                }
            );
        }
    };

export const DETAIL_PANEL_REQUIRED_FIELDS = [
    "lock_uid",
    "shortcut_document_id",
    "res_name",
    "res_model_name",
    "file_size",
    "res_model",
    "mail_alias_domain_count",
    "alias_name",
    "alias_domain_id",
    "create_activity_type_id",
    "is_protected",
    "type",
    "name",
    "folder_id",
    "company_id",
    "owner_id",
    "user_permission",
    "partner_id",
    "tag_ids",
];
