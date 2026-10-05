import { onMounted, useListener, useProps } from "@odoo/owl";
import { useCommand } from "@web/core/commands/command_hook";
import { FileUploadProgressContainer } from "@web/core/file_upload/file_upload_progress_container";
import { FileUploadProgressDataRow } from "@web/core/file_upload/file_upload_progress_record";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_utils";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ListRenderer } from "@web/views/list/list_renderer";

import { DocumentsRightPanel } from "@documents/components/documents_right_panel/documents_right_panel";
import { DocumentsRendererMixin, previewProps } from "@documents/views/documents_renderer_mixin";
import { DocumentsActionHelper } from "@documents/views/helper/documents_action_helper";
import { useDraggableDocuments } from "@documents/views/helper/documents_draggable";
import { DocumentsDropZone } from "@documents/views/helper/documents_drop_zone";
import { DocumentsFileViewer } from "@documents/views/helper/documents_file_viewer";

export class DocumentsListRendererCommon extends ListRenderer {
    documentsAttachmentViewerProps = useProps(previewProps);
    static template = "documents.DocumentsListRendererCommon";
    static components = Object.assign({}, ListRenderer.components, {
        DocumentsFileViewer,
    });

    onCellClicked(record, column, ev) {
        if (ev.target.closest(".o_field_documents_type_icon")) {
            this.onIconClicked(record, ev);
            return;
        }
        super.onCellClicked(...arguments);
    }

    onIconClicked(record, ev) {
        record.onClickPreview(ev);
    }
}

export class DocumentsListRenderer extends DocumentsRendererMixin(DocumentsListRendererCommon) {
    static template = "documents.DocumentsListRenderer";
    static recordRowTemplate = "documents.DocumentsListRenderer.RecordRow";
    static components = Object.assign({}, DocumentsListRendererCommon.components, {
        FileUploadProgressContainer,
        FileUploadProgressDataRow,
        DocumentsDropZone,
        DocumentsActionHelper,
        DocumentsRightPanel,
    });

    setup() {
        super.setup();
        const { uploads } = useService("file_upload");

        this.documentUploads = uploads;
        useCommand(
            _t("Select all"),
            () => {
                const allSelected =
                    this.props.list.selection.length === this.props.list.records.length;
                this.props.list.records.forEach((record) => {
                    record.toggleSelection(!allSelected);
                });
                const focusedRecord = this.setDefaultFocus();
                document
                    .querySelector(
                        `.o_data_row[data-value-id="${focusedRecord.resId}"] .o_data_cell`
                    )
                    .focus();
            },
            {
                category: "smart_action",
                hotkey: "control+a",
            }
        );

        useDraggableDocuments({
            ref: this.rootRef,
            model: this.env.model,
            targetSelector: ".o_data_row.o_folder_record",
            elements: ".o_data_row",
            preventDrag: () =>
                this.env.searchModel.getSelectedFolderId() === "TRASH" ||
                this.getIsDomainSelected(),
            onTargetPointerEnter: ({ addClass, target, isInvalid }) => {
                addClass(target, isInvalid ? "table-danger" : "table-success");
            },
            onTargetPointerLeave: ({ removeClass, target }) => {
                removeClass(target, "table-danger", "table-success");
            },
        });

        onMounted(() =>
            this.documentService.scrollToFirstSelectedRecord(
                ".o_data_row.o_data_row_selected",
                "center"
            )
        );
        useListener(window, "keydown", (ev) => this.onKeyDown(ev));
        useListener(window, "keyup", (ev) => this.onKeyUp(ev));
    }

    getRowClass(record) {
        let classes = super.getRowClass(record);
        if (record.data.type === "folder") {
            classes += " o_folder_record";
        }
        return classes;
    }

    /**
     * Called when a keydown event is triggered.
     */
    onGlobalKeydown(ev) {
        if ((ev.key !== "Enter" && ev.key !== " ") || this.editedRecord) {
            return;
        }
        const row = ev.target.closest(".o_data_row");
        const record = row && this.props.list.records.find((rec) => rec.id === row.dataset.id);
        if (!record) {
            return;
        }
        if (ev.key === "Enter" && record.data.type !== "folder") {
            record.onClickPreview(ev);
        }
        ev.stopPropagation();
        ev.preventDefault();
        this.toggleRecordSelection(record);
    }

    onKeyDown(ev) {
        if (this.rootRef() && ev.key === "Control") {
            this.rootRef().classList.add("o_documents_dnd_shortcut");
        }
    }

    onKeyUp(ev) {
        if (this.rootRef() && ev.key === "Control") {
            this.rootRef().classList.remove("o_documents_dnd_shortcut");
        }
    }

    /**
     * Upon clicking on a record, opens the folder/preview the file.
     * If ctrl or shift key pressed, selects/unselects the record.
     * If the column is editable, the record is selected and click
     * without ctrl or shift pressed, edits the column.
     */
    onCellClicked(record, column, ev) {
        ev.stopPropagation();
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) {
            this.toggleRecordSelection(record, ev);
            return;
        }
        if (!ev.target.closest(".o_field_documents_type_icon")) {
            this.documentService.focusRecord(record);
            if (!(record.selected && this.editableColumns.includes(column.name))) {
                return;
            }
        }
        super.onCellClicked(...arguments);
    }

    /**
     * @override handles the folder.
     */
    onIconClicked(record, ev) {
        if (record.data.type === "folder") {
            record.openFolder();
            return;
        }
        super.onIconClicked(record, ev);
    }

    get editableColumns() {
        const standardEditable = [
            "name",
            "tag_ids",
            "partner_id",
            "owner_id",
            "company_id",
            "folder_id",
        ];
        const customEditable = this.columns
            .filter((col) => col.name.startsWith("x_") && !col.readonly)
            .map((col) => col.name);
        return standardEditable.concat(customEditable);
    }

    /**
     * Called when a click event is triggered.
     */
    onGlobalClick(ev) {
        const target = ev.target;
        // A tag's delete button only exists while the cell is editable, leaving
        // edit mode here would destroy it before its callback runs
        if (target.closest(".o_data_row.o_selected_row")) {
            return;
        }
        // Ignore clicks in an overlay above us (e.g. a "Search More..." dialog)
        if (this.activeElement !== this.uiService.activeElement) {
            return;
        }
        this.props.list.leaveEditMode();

        // We have to check that we are indeed clicking in the list view as on mobile,
        // the inspector renders above the renderer but it still triggers this event.
        if (target.closest(".o_data_row") || !this.rootRef()?.contains(target)) {
            return;
        }
        if (target.closest(".o_documents_view thead")) {
            return; // We then have to check that we are not clicking on the header
        }
        this.documentService.focusRecord(this.env.model.getContainerRecord());
        this.props.list.selection.forEach((el) => el.toggleSelection(false));
    }

    getFolderInfo() {
        return {
            count: this.props.list.count,
            fileSize: this.props.list.model.fileSize,
        };
    }

    /**
     * @override to update focusedRecord when navigating with arrow keys
     */
    findFocusFutureCell(cell, cellIsInGroupRow, direction) {
        const futureCell = super.findFocusFutureCell(cell, cellIsInGroupRow, direction);
        if (futureCell) {
            const dataPointId = futureCell.closest("tr").dataset.id;
            const record = this.props.list.records.filter((x) => x.id === dataPointId)[0];
            if (record) {
                this.documentService.focusRecord(record);
            }
        }
        return futureCell;
    }

    onCellKeydown(ev, group = null, record = null) {
        const hotkey = getActiveHotkey(ev);
        if (hotkey === "enter") {
            return;
        }
        return super.onCellKeydown(...arguments);
    }

    get hasSelectors() {
        return this.props.allowSelectors;
    }

    get isMobile() {
        return this.uiService.isSmall;
    }

    toggleRecordSelection(record) {
        const isSelection = record && !record.selected;
        super.toggleRecordSelection(record);
        if (isSelection) {
            this.documentService.focusRecord(record, true);
        }
    }

    toggleSelection() {
        super.toggleSelection();
        if (this.canSelectRecord) {
            this.setDefaultFocus();
        }
    }
}
