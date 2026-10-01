import { stores } from "@odoo/o-spreadsheet";
import { Domain } from "@web/core/domain";
import { range } from "@web/core/utils/numbers";

const { SidePanelStore } = stores;

/**
 * Get the function that have to be executed to insert the given list in the
 * given spreadsheet. The returned function has to be called with the model
 * of the spreadsheet and the dataSource of this list
 *
 * @private
 *
 * @param {import("@spreadsheet/list/plugins/list_core_plugin").SpreadsheetList} list
 * @param {object} param
 * @param {number} param.threshold
 * @param {object} param.fields fields coming from list_model
 * @param {string} param.name Name of the list
 *
 * @returns {function}
 */
export function insertList({ list, threshold, name }) {
    const definition = {
        model: list.model,
        domain: new Domain(list.domain).toJson(),
        context: list.context,
        orderBy: list.orderBy,
        name,
        actionXmlId: list.actionXmlId,
        columns: list.columns,
    };
    return async (model, stores) => {
        const listId = model.getters.getNextListId();
        const result = model.dispatch("INSERT_NEW_ODOO_LIST", {
            listId,
            name: definition.name,
            linesNumber: threshold,
            definition,
            insertInNewSheet: !this.isEmptySpreadsheet,
            mode: "static",
        });

        if (!result.isSuccessful) {
            throw new Error(`Couldn't insert list in spreadsheet. Reasons : ${result.reasons}`);
        }
        const dataSource = model.getters.getListDataSource(listId);
        await dataSource.load();
        const columns = range(0, definition.columns.length);
        const sheetId = model.getters.getActiveSheetId();
        model.dispatch("AUTORESIZE_COLUMNS", { sheetId, cols: columns });
        const rows = range(0, threshold + 1);
        model.dispatch("AUTORESIZE_ROWS", { sheetId, rows });

        const sidePanel = stores.get(SidePanelStore);
        sidePanel.open("LIST_PROPERTIES_PANEL", { listId });
    };
}
