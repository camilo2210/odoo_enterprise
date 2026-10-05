import { useProps } from "@odoo/owl";
import { render } from "@web/owl2/utils";
import { _t } from "@web/core/l10n/translation";
import { KanbanRecord, kanbanRecordProps } from "@web/views/kanban/kanban_record";
import { browser } from "@web/core/browser/browser";
import { FileUploadProgressBar } from "@web/core/file_upload/file_upload_progress_bar";
import { usePopover } from "@web/core/popover/popover_hook";
import { useBus, useService } from "@web/core/utils/hooks";
import { TEXT_MIMETYPES } from "@web/core/file_viewer/file_model";
import { DocumentsActionPopover } from "./documents_kanban_actions_popover";

const CANCEL_GLOBAL_CLICK = ["a", ".dropdown", ".oe_kanban_action"].join(",");

export class DocumentsKanbanRecord extends KanbanRecord {
    static components = {
        ...KanbanRecord.components,
        FileUploadProgressBar,
    };
    props = useProps(kanbanRecordProps);
    static template = "documents.DocumentsKanbanRecord";

    setup() {
        super.setup();
        // File upload
        const { bus, uploads } = useService("file_upload");
        this.documentUploads = uploads;
        useBus(bus, "FILE_UPLOAD_ADDED", (ev) => {
            if (ev.detail.upload.data.get("document_id") === this.props.record.resId) {
                render(this, true);
            }
        });

        this.uiService = useService("ui");
        this.thumbnailService = useService("documents_client_thumbnail");
        this.thumbnailService.enqueueRecords([this.props.record]);

        // Activity updates from Chatter
        this.documentService = useService("document.document");
        useBus(this.documentService.bus, "DOCUMENT_CHATTER_ACTIVITY_CHANGED", ({ detail }) => {
            if (this.props.record.data.id === detail.recordId) {
                this.props.record.load();
            }
        });
        const popoverOptions = {
            onClose: () => {
                this.anchor?.remove();
                this.rootRef()?.focus();
            },
            popoverClass: "o_document_record_popover o-dropdown--menu dropdown-menu",
            position: "bottom-start",
        };
        this.popover = usePopover(DocumentsActionPopover, popoverOptions);
    }

    /**
     * @override
     */
    getCardClasses() {
        let result = super.getCardClasses();
        if (this.props.record.selected) {
            result += " o_record_selected";
        }
        if (this.props.record.isRequest()) {
            result += " oe_file_request";
        }
        if (this.props.record.data.type === "folder") {
            result += " o_folder_record";
        }
        if (this.uiService.isSmall && this.props.groupByField?.name === "last_access_date_group") {
            result += " flex-grow-1";
        }
        return result;
    }

    get renderingContext() {
        const context = super.renderingContext;
        const record = this.props.record;
        context.encodeURIComponent = encodeURIComponent;

        if ([false, "TRASH", "RECENT"].includes(this.env.searchModel.getSelectedFolderId())) {
            context.inFolder =
                record.data.folder_id?.display_name ||
                {
                    MY: _t("My Drive"),
                    COMPANY: _t("Company"),
                    SHARED: _t("Shared with me"),
                }[record.data.user_folder_id];
        }
        context.mimetype = record.shortcutTarget.data.mimetype;
        const RENDERED_MIMETYPES = [...TEXT_MIMETYPES, "application/documents-email"];
        if (RENDERED_MIMETYPES.includes(context.mimetype) && !record.data.has_embedded_pdf) {
            const token = encodeURIComponent(record.data.access_token);
            const rawChecksum = context.record.checksum?.raw_value;
            const checksum = rawChecksum ? encodeURIComponent(rawChecksum) : "";
            context.thumbnailUrl = `/documents/render_text/${token}?head=1${
                checksum ? `&unique=${checksum}` : ""
            }`;
        }

        return context;
    }
    /**
     * Get the current file upload for this record if there is any
     */
    getFileUpload() {
        return Object.values(this.documentUploads).find(
            (upload) => upload.data.get("document_id") === this.props.record.resId
        );
    }

    /**
     * @override
     */
    onGlobalClick(ev) {
        if (ev.target.closest(CANCEL_GLOBAL_CLICK)) {
            return;
        }
        const selectionLength = this.props.getSelection().length;
        // We can enable selection mode when only one item is selected if a key is pressed,
        // or if we have more than one item selected
        const isSelectionModeActive = selectionLength === 1 ? ev.shiftKey : selectionLength > 1;
        const selectionKeyActive = ev.altKey || ev.ctrlKey;
        if (
            ev.target.closest("div[name='document_preview']") &&
            !(selectionKeyActive || ev.shiftKey)
        ) {
            this.props.record.onClickPreview(ev);
        } else if (selectionKeyActive || isSelectionModeActive) {
            this.rootRef()?.focus();
            this.props.toggleSelection(this.props.record, ev.shiftKey);
        } else if (
            this.env.searchModel.getSelectedFolderId() === "TRASH" ||
            this.props.record.data.type !== "folder"
        ) {
            // Select only one document record
            this.props.getSelection().forEach((r) => r.toggleSelection(false));
            this.rootRef()?.focus();
            this.props.toggleSelection(this.props.record);
        } else {
            this.props.record.openFolder();
        }
    }

    onTouchStart() {
        // We handle touch multi-selection for Documents with a long
        // press as well, as a simple touch already selects one record
        this.touchStartMs = Date.now();
        if (this.longTouchTimer === null) {
            this.longTouchTimer = browser.setTimeout(() => {
                if (!this.props.record.selected) {
                    this.props.toggleSelection(this.props.record);
                }
                this.resetLongTouchTimer();
            }, this.LONG_TOUCH_THRESHOLD);
        }
    }

    async onContextMenu(ev) {
        if (this.env.searchModel.context.documents_view_secondary) {
            return;
        }
        if (!this.props.record.selected) {
            await Promise.all(
                this.props.getSelection().map(async (r) => {
                    if (r.selected) {
                        await r.toggleSelection(false);
                    }
                })
            );
            this.rootRef()?.focus();
            await this.props.toggleSelection(this.props.record);
        }
        if (this.uiService.isSmall) {
            document.querySelector(".o_cp_action_menus button")?.click();
            return;
        }
        this.anchor = document.createElement("div");
        this.anchor.style.cssText = `position:fixed;width:0;height:0;top:${ev.clientY}px;left:${ev.clientX}px;`;
        document.body.appendChild(this.anchor);
        this.popover.open(this.anchor, {
            targetRecords: this.env.model.root.selection,
            folderId: this.env.searchModel.getSelectedFolderId(),
            isPreview: true,
        });
    }
}
