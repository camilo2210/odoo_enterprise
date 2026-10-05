import * as spreadsheet from "@odoo/o-spreadsheet";
import { initCallbackRegistry } from "@spreadsheet/o_spreadsheet/init_callbacks";
import { buildViewLink } from "@spreadsheet/ir_ui_menu/odoo_menu_link_cell";

const { markdownLink } = spreadsheet.links;
const { UuidGenerator } = spreadsheet.helpers;

/**
 * Helper to get the function to be called when the spreadsheet is opened
 * in order to insert the link.
 * @param {import("@spreadsheet/ir_ui_menu/odoo_menu_link_cell").ViewLinkDescription} actionToLink
 * @returns Function to call
 */
function insertLink(actionToLink) {
    return (model) => {
        if (!this.isEmptySpreadsheet) {
            const sheetId = UuidGenerator.smallUuid();
            const sheetIdFrom = model.getters.getActiveSheetId();
            model.dispatch("CREATE_SHEET", {
                sheetId,
                position: model.getters.getSheetIds().length,
                name: model.getters.getNextSheetName(),
            });
            model.dispatch("ACTIVATE_SHEET", { sheetIdFrom, sheetIdTo: sheetId });
        }
        const viewLink = buildViewLink(actionToLink);
        model.dispatch("UPDATE_CELL", {
            sheetId: model.getters.getActiveSheetId(),
            content: markdownLink(actionToLink.name, viewLink),
            col: 0,
            row: 0,
        });
    };
}

initCallbackRegistry.add("insertLink", insertLink);
