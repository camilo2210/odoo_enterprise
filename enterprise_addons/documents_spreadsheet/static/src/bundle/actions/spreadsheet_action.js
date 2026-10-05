import { onWillStart, proxy } from "@odoo/owl";
import { useSubEnv } from "@web/owl2/utils";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

import { Model, registries, helpers } from "@odoo/o-spreadsheet";
import { UNTITLED_SPREADSHEET_NAME } from "@spreadsheet/helpers/constants";
import { AbstractSpreadsheetAction } from "@spreadsheet_edition/bundle/actions/abstract_spreadsheet_action";
import { _t } from "@web/core/l10n/translation";
import { patchSpreadsheetExternalShareFunctionCheck } from "./external_share_function";
import { user } from "@web/core/user";

const { topbarMenuRegistry } = registries;
const { doesCellContainFunction } = helpers;

export class SpreadsheetAction extends AbstractSpreadsheetAction {
    static template = "documents_spreadsheet.SpreadsheetAction";
    static path = "spreadsheet";
    static displayName = _t("Spreadsheet");

    resModel = "documents.document";
    threadField = "document_id";

    setup() {
        super.setup();
        this.state = proxy({
            isFavorited: false,
            spreadsheetName: UNTITLED_SPREADSHEET_NAME,
            isSharedExternally: false,
        });
        this.threadId = this.params?.thread_id;
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.documentService = useService("document.document");
        this._canSaveAsTemplate = false;
        onWillStart(async () => {
            this._canSaveAsTemplate = await user.hasGroup("documents.group_documents_user");
        });
        useSubEnv({
            newSpreadsheet: this.createNewSpreadsheet.bind(this),
            makeCopy: this.makeCopy.bind(this),
            canSaveAsTemplate: this.canSaveAsTemplate.bind(this),
            saveAsTemplate: this.saveAsTemplate.bind(this),
            onShareSpreadsheet: this.shareSpreadsheet.bind(this),
            onFreezeAndShareSpreadsheet: this.freezeAndShareSpreadsheet.bind(this),
            isFrozenSpreadsheet: () => this.data.handler === "frozen_spreadsheet",
            moveToTrash: this.moveToTrash.bind(this),
            takeOutOfTrash: this.takeOutOfTrash.bind(this),
            isArchived: () => this.data.is_archived,
            hasWriteAccess: () => this.data.has_write_access,
            isSharedExternally: () => this.state.isSharedExternally,
        });
        const patchedFunctions = patchSpreadsheetExternalShareFunctionCheck();
        useBus(this.documentService.bus, "DOCUMENT_RELOAD", async () => {
            const [{ is_shared_externally }] = await this.orm.read(
                this.resModel,
                [this.resId],
                ["is_shared_externally"]
            );
            if (this.state.isSharedExternally !== is_shared_externally) {
                // force an evaluation to invalidate forbidden standalone functions.
                this.state.isSharedExternally = is_shared_externally;
                const cellIds = [];
                for (const sheetId of this.model.getters.getSheetIds()) {
                    for (const cell of this.model.getters.getCells(sheetId)) {
                        for (const funcName of patchedFunctions) {
                            if (doesCellContainFunction(cell, funcName)) {
                                cellIds.push(cell.id);
                            }
                        }
                    }
                }
                this.model.dispatch("EVALUATE_CELLS", cellIds);
            }
        });
    }

    /**
     * @override
     */
    _initializeWith(data) {
        super._initializeWith(data);
        this.state.isFavorited = data.is_favorited;
        this.state.isSharedExternally = data.is_shared_externally;
        this.isArchived = data.is_archived;
    }

    get navbarProps() {
        return {
            ...super.navbarProps,
            isReadonly: this.spreadsheetMode === "readonly",
        };
    }

    get spreadsheetMode() {
        return !this.hasWriteAccess || this.isArchived ? "readonly" : "normal";
    }

    /**
     * @param {OdooEvent} ev
     * @returns {Promise}
     */
    async _onSpreadSheetFavoriteToggled(ev) {
        this.state.isFavorited = !this.state.isFavorited;
        await this.documentService.toggleFavorites([this.resId], false);
    }

    /**
     * Create a new sheet and display it
     */
    async createNewSpreadsheet() {
        const action = await this.orm.call("documents.document", "action_open_new_spreadsheet");
        this.actionService.doAction(action, { clear_breadcrumbs: true });
    }

    onSpreadsheetLeftUpdateVals() {
        return {
            ...super.onSpreadsheetLeftUpdateVals(),
            is_multipage: this.model.getters.getSheetIds().length > 1,
        };
    }

    canSaveAsTemplate() {
        return this._canSaveAsTemplate;
    }
    /**
     * @private
     * @returns {Promise}
     */
    async saveAsTemplate() {
        const model = new Model(this.model.exportData(), {
            custom: {
                env: this.env,
                odooDataProvider: this.model.config.custom.odooDataProvider,
            },
        });
        const data = model.exportData();
        const name = this.state.spreadsheetName;

        this.actionService.doAction("documents_spreadsheet.save_spreadsheet_template_action", {
            additionalContext: {
                default_template_name: _t("%s - Template", name),
                default_spreadsheet_data: JSON.stringify(data),
                default_thumbnail: this.getThumbnail(),
            },
        });
    }

    /**
     * @returns <string> the url to share the spreadsheet
     */
    shareSpreadsheet() {
        this.documentService.openSharingDialog([this.resId]);
    }

    async freezeAndShareSpreadsheet() {
        if (this.data.handler === "frozen_spreadsheet") {
            this.notification.add(_t("You can not freeze a frozen spreadsheet"));
            return;
        }

        const { freezeOdooData } = odoo.loader.modules.get("@spreadsheet/helpers/model");
        this.model.dispatch("LOG_DATASOURCE_EXPORT", { action: "freeze" });
        const data = await freezeOdooData(this.model);
        const files = await this.model.exportXLSX();
        this.model.dispatch("LOG_DATASOURCE_EXPORT", { action: "freeze" });
        const record = await this.orm.call("documents.document", "action_freeze_and_copy", [
            this.resId,
            JSON.stringify(data),
            files.files,
        ]);
        this.documentService.openSharingDialog([record.id]);
    }

    async moveToTrash() {
        const wasArchived = await this.documentService.moveToTrash([this.resId]);
        if (!wasArchived) {
            return;
        }
        if (this.env.config.breadcrumbs.length > 1) {
            await this.actionService.restore();
        } else {
            await this.actionService.doAction("documents.document_action");
        }
        this.notification.add(_t("Spreadsheet moved to trash"), { type: "success" });
    }

    async takeOutOfTrash() {
        await this.orm.call("documents.document", "action_unarchive", [this.resId]);
        this.actionService.doAction("reload_context");
    }
}

registry.category("actions").add("action_open_spreadsheet", SpreadsheetAction, { force: true });

topbarMenuRegistry.addChild("move_to_trash", ["file"], {
    name: _t("Move to trash"),
    sequence: 80,
    isVisible: (env) => env.isArchived && !env.isArchived() && !!env.moveToTrash,
    execute: (env) => env.moveToTrash(),
    icon: "o-spreadsheet-Icon.TRASH_FILLED",
    isEnabledOnLockedSheet: true,
});
