import { computed, t, useProps, useOnChange } from "@odoo/owl";
import { useCommand } from "@web/core/commands/command_hook";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";

export const previewProps = {
    previewStore: t.object({
        attachments: t.array(t.object()).optional(),
        startIndex: t.number().optional(),
    }),
};

/**
 * @template {import("@odoo/owl").ComponentConstructor} T
 * @param {T} RendererComponent
 */
export const DocumentsRendererMixin = (RendererComponent) =>
    class extends RendererComponent {
        documentsAttachmentViewerProps = useProps(previewProps);

        setup() {
            super.setup();

            this.documentService = useService("document.document");
            this.documentService.focusRecord(
                this.selection?.[0] || this.env.model.getContainerRecord(),
                true
            );

            useCommand(_t("Trash"), () => this.env.model.onArchive(), {
                category: "smart_action",
                hotkey: "control+m",
                isAvailable: () =>
                    this.documentService.userIsInternal &&
                    this.recordsToArchive() &&
                    this.selection.every((r) => r.data.user_permission === "edit"),
            });
            useCommand(_t("Delete"), () => this.env.model.onDelete(), {
                category: "smart_action",
                hotkey: "control+d",
                isAvailable: () => this.recordsToDelete() && this.env.model.canDeleteRecords,
            });
            useCommand(
                _t("Toggle favorite"),
                async () => {
                    if (this.selection.length) {
                        await this.documentService.toggleFavorites(
                            this.selection.map((r) => r.resId)
                        );
                    }
                },
                {
                    category: "smart_action",
                    hotkey: "alt+t",
                    isAvailable: () => this.selection.length,
                }
            );
            this.recordsToDelete = computed(() =>
                !this.documentService.userIsInternal
                    ? this.selection
                    : this.selection.some((r) => !r.data.active)
            );
            this.recordsToArchive = computed(() => this.selection.some((r) => r.data.active));

            useOnChange(
                () => [this.props.list, this.props.records],
                () =>
                    this.documentService.focusRecord(
                        this.selection?.[0] || this.getDefaultRefreshFocus()
                    ),
                { initialRun: false }
            );
            useBus(this.documentService.bus, "UPDATE-DOCUMENT-FOLDER", (ev) => {
                if (
                    this.documentService.ui.isSmall &&
                    this.documentService.state.rightPanelVisible
                ) {
                    // Avoid empty view by resetting chatter on selection removal
                    this.documentService.toggleRightPanelVisibility();
                }
                this.documentService.focusRecord(this.env.model.getContainerRecord());
            });
        }
        /**
         * Default focus on first record (fallback on container record)
         * if there is no focused record or current focused record is out of the record list.
         */
        setDefaultFocus() {
            const focusedRecord = this.documentService.focusedRecord;
            const records = this.props.list ? this.props.list.records : this.props.records;
            if (!focusedRecord || !records.find((r) => r.id === focusedRecord.id)) {
                const record =
                    this.env.config.viewType === "kanban"
                        ? records.find((r) => r.data.type === "folder") || records[0]
                        : records[0];
                this.documentService.focusRecord(
                    record || this.env.model.getContainerRecord(),
                    true
                );
            }
            return this.documentService.focusedRecord;
        }
        /**
         * Record to select when refreshing focus if there is no selection.
         */
        getDefaultRefreshFocus() {
            return this.env.model.getContainerRecord();
        }

        getIsDomainSelected() {
            if (this.env.model.isDomainSelected) {
                this.env.model.notification.add(_t("Only current page items can be dragged."), {
                    type: "info",
                });
            }
            return this.env.model.isDomainSelected;
        }

        /**
         * Number of documents in the current (container) folder
         */
        getNbViewItems() {
            if (!this.props.list) {
                return this.props.records.length;
            }
            return this.props.list.count;
        }

        get selection() {
            if (!this.props.list) {
                return this.props.records.filter((r) => r.selected);
            }
            return this.props.list.selection;
        }
    };
