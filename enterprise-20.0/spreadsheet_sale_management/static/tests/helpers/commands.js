import { helpers, stores } from "@odoo/o-spreadsheet";

import { makeStoreWithModel } from "@spreadsheet/../tests/helpers/stores";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { getSaleOrderSpreadsheetData } from "./data";

const { AutofillStore, ClipboardStore } = stores;
const { toCartesian, toZone } = helpers;

export async function createSaleOrderSpreadsheetModel() {
    const data = getSaleOrderSpreadsheetData();
    const returnValue = await createModelWithDataSource({
        spreadsheetData: data,
    });
    makeStoreWithModel(returnValue.model, AutofillStore);
    makeStoreWithModel(returnValue.model, ClipboardStore);
    return returnValue;
}

/**
 * @param {import("@odoo/o-spreadsheet").Model} model
 * @param {string} xc
 * @param {string} fieldName
 * @param {number} indexInList
 * @param {string} sheetId
 */
export function addFieldSync(
    model,
    xc,
    fieldName,
    indexInList,
    sheetId = model.getters.getActiveSheetId()
) {
    return model.dispatch("ADD_FIELD_SYNC", {
        sheetId,
        ...toCartesian(xc),
        listId: model.getters.getMainSaleOrderLineList().id,
        indexInList,
        fieldName,
    });
}

export function deleteFieldSyncs(model, xc, sheetId = model.getters.getActiveSheetId()) {
    return model.dispatch("DELETE_FIELD_SYNCS", { sheetId, zone: toZone(xc) });
}
