import { _t } from "@web/core/l10n/translation";
import { helpers } from "@odoo/o-spreadsheet";
import { OdooUIPlugin } from "@spreadsheet/plugins";

const { sanitizeSheetName, getUniqueText, UuidGenerator } = helpers;

export class PivotOdooInsertion extends OdooUIPlugin {
    static getters = /** @type {const} */ ([]);

    /**
     * Handle a spreadsheet command
     * @param {Object} cmd Command
     */
    handle(cmd) {
        switch (cmd.type) {
            case "INSERT_NEW_ODOO_PIVOT":
                this.insertNewOdooPivot(
                    cmd.pivotId,
                    cmd.pivotName,
                    cmd.tableExport,
                    cmd.insertInNewSheet,
                    cmd.mode
                );
                break;
        }
    }

    /** Insert a new pivot (OdooPivot) and add a sheet for it if needed. */
    insertNewOdooPivot(pivotId, pivotName, tableExport, insertInNewSheet, mode) {
        const sheetName = this._computePivotSheetName(pivotId, pivotName);
        if (insertInNewSheet) {
            this._createAndActivateSheet(sheetName);
        } else {
            this._renameCurrentSheet(sheetName);
        }

        const sheetId = this.getters.getActiveSheetId();
        this.dispatch("INSERT_PIVOT_WITH_TABLE", {
            sheetId,
            col: 0,
            row: 0,
            pivotId,
            table: tableExport,
            pivotMode: mode,
        });
    }

    _computePivotSheetName(pivotId, pivotName) {
        const name = _t("%(pivot_name)s (Pivot #%(pivot_id)s)", {
            pivot_name: pivotName,
            pivot_id: this.getters.getPivotFormulaId(pivotId),
        });
        const sanitized = sanitizeSheetName(name);
        const allNames = this.getters.getSheetIds().map((id) => this.getters.getSheetName(id));
        return getUniqueText(sanitized, allNames);
    }

    _renameCurrentSheet(sheetName) {
        const sheetId = this.getters.getActiveSheetId();
        this.dispatch("RENAME_SHEET", {
            sheetId,
            oldName: this.getters.getSheetName(sheetId),
            newName: sheetName,
        });
    }

    _createAndActivateSheet(sheetName) {
        const newSheetId = UuidGenerator.smallUuid();
        this.dispatch("CREATE_SHEET", {
            sheetId: newSheetId,
            position: this.getters.getSheetIds().length,
            name: sheetName,
        });
        this.dispatch("ACTIVATE_SHEET", {
            sheetIdFrom: this.getters.getActiveSheetId(),
            sheetIdTo: newSheetId,
        });
    }
}
