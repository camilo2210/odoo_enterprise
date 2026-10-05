import {
    STATIC_COG_GROUP_ACTION_BASE,
    STATIC_COG_GROUP_ACTION_NATIVE,
} from "@documents/views/cog_menu/documents_cog_menu_group";
import { XLSX_MIME_TYPES } from "@documents_spreadsheet/helpers";
import { TemplateDialog } from "@documents_spreadsheet/spreadsheet_template/spreadsheet_template_dialog";
import { loadBundle } from "@web/core/assets";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export const DocumentsSpreadsheetControllerMixin = () => ({
    /**
     * Prevents spreadsheets from being in the viewable attachments list
     * when previewing a file in the FileViewer.
     *
     * @override
     */
    isRecordPreviewable(record) {
        return (
            super.isRecordPreviewable(...arguments) &&
            !["spreadsheet", "frozen_spreadsheet"].includes(record.data.handler)
        );
    },

    /**
     * @override
     */
    async onOpenDocumentsPreview({ mainDocument }) {
        const mainDocumentOrTarget = mainDocument.shortcutTarget;
        if (["spreadsheet", "frozen_spreadsheet"].includes(mainDocumentOrTarget.data.handler)) {
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "action_open_spreadsheet",
                params: {
                    spreadsheet_id: mainDocumentOrTarget.resId,
                },
            });
        } else if (
            XLSX_MIME_TYPES.includes(mainDocumentOrTarget.data.mimetype) ||
            mainDocumentOrTarget.data.mimetype === "text/csv"
        ) {
            // Keep MainDocument as `active` can be different for shortcut and target.
            if (!mainDocument.data.active) {
                this.dialogService.add(ConfirmationDialog, {
                    title: _t("Restore file?"),
                    body: _t(
                        "Spreadsheet files cannot be handled from the Trash. Would you like to restore this document?"
                    ),
                    cancel: () => {},
                    confirm: async () => {
                        await this.orm.call("documents.document", "action_unarchive", [
                            mainDocument.resId,
                        ]);
                        this.env.searchModel.toggleCategoryValue(
                            1,
                            mainDocument.data.folder_id.id ?? false
                        );
                    },
                    confirmLabel: _t("Restore"),
                });
            } else if (this.documentService.userIsInternal) {
                this.actionService.doAction("documents_spreadsheet.import_to_spreadsheet_action", {
                    additionalContext: { default_document_id: mainDocumentOrTarget.resId },
                });
            }
        } else {
            return super.onOpenDocumentsPreview(...arguments);
        }
    },

    async onClickCreateSpreadsheet(ev) {
        const folderId = this.env.searchModel.getSelectedFolderId() || undefined;
        const context = this.props.context;
        if (folderId === "COMPANY") {
            context.default_owner_id = false;
        }
        this.dialogService.add(TemplateDialog, {
            folderId,
            context,
            folders: this.env.searchModel
                .getFolders()
                .filter((folder) => folder.id && typeof folder.id === "number"),
        });
    },

    async onClickFreezeAndShareSpreadsheet() {
        const selection = this.targetRecords;
        if (
            selection.length !== 1 ||
            !["spreadsheet", "frozen_spreadsheet"].includes(selection[0].data.handler)
        ) {
            this.notification.add(_t("Select one and only one spreadsheet"));
            return;
        }

        const doc = selection[0];

        // Freeze the spreadsheet
        await loadBundle("spreadsheet.o_spreadsheet");
        const { fetchSpreadsheetModel, freezeOdooData } = odoo.loader.modules.get(
            "@spreadsheet/helpers/model"
        );
        const model = await fetchSpreadsheetModel(this.env, "documents.document", doc.resId);
        const spreadsheetData = JSON.stringify(await freezeOdooData(model));
        const excelFiles = await model.exportXLSX();
        const files = excelFiles.files;
        model.dispatch("LOG_DATASOURCE_EXPORT", { action: "freeze" });

        // Create a new <documents.document> with the frozen data
        const record = await this.orm.call("documents.document", "action_freeze_and_copy", [
            doc.resId,
            spreadsheetData,
            files,
        ]);

        await this.env.searchModel._reloadSearchModel(true);
        await this.documentService.openSharingDialog([record.id]);
    },

    getTopBarActionMenuItems() {
        const menuItems = super.getTopBarActionMenuItems();
        menuItems.download.isAvailable = () =>
            this.model.targetRecords.some(
                (r) => !r.isRequest() && r.data.handler !== "spreadsheet" && r.data.type !== "url"
            );
        return {
            ...menuItems,
            freezeAndShare: {
                isAvailable: () =>
                    this.documentService.userIsInternal &&
                    this.targetRecords.length === 1 &&
                    this.targetRecords[0]?.data?.handler === "spreadsheet",
                sequence: 30,
                description: _t("Freeze and Share"),
                icon: "share",
                callback: () => this.onClickFreezeAndShareSpreadsheet(),
                groupNumber: STATIC_COG_GROUP_ACTION_BASE,
            },
        };
    },

    getStaticActionMenuItems() {
        const menuItems = super.getStaticActionMenuItems(...arguments);
        // Not present in activity view
        if (menuItems.insert) {
            menuItems.insert.isAvailable = () => this.documentService.userIsInternal;
            menuItems.insert.iconClass = "invisible";
            menuItems.insert.sequence = 110;
            menuItems.insert.groupNumber = STATIC_COG_GROUP_ACTION_NATIVE;
        }

        const superVersionIsAvailable = menuItems.version.isAvailable;
        menuItems.version.isAvailable = () =>
            superVersionIsAvailable() &&
            !["spreadsheet", "frozen_spreadsheet"].includes(
                this.model.targetRecords[0].data.handler
            );

        return menuItems;
    },
});
