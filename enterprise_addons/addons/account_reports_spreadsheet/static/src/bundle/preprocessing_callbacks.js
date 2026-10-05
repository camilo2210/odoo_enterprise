import * as spreadsheet from "@odoo/o-spreadsheet";
const { UuidGenerator, sanitizeSheetName, getUniqueText } = spreadsheet.helpers;

import { initCallbackRegistry } from "@spreadsheet/o_spreadsheet/init_callbacks";

function computeValidSheetName(name, allNames) {
    const sanitized = sanitizeSheetName(name);
    return getUniqueText(sanitized, allNames);
}

export function workingFilePreprocessingAction({ subActionData, subAction }) {
    const subActionInitCallback = initCallbackRegistry.get(subAction).bind(this)(subActionData);

    return async (model, stores) => {
        const name = subActionData.name;
        const allExistingSheetNames = model.getters
            .getSheetIds()
            .map((id) => model.getters.getSheetName(id));
        const sheetName = computeValidSheetName(name, allExistingSheetNames);

        if (this.isNewSpreadsheet) {
            const sheetId = model.getters.getActiveSheetId();
            model.dispatch("RENAME_SHEET", {
                sheetId,
                oldName: model.getters.getSheetName(sheetId),
                newName: sheetName,
            });
        } else {
            const sheetIdFrom = model.getters.getActiveSheetId();
            const sheetId = UuidGenerator.smallUuid();
            model.dispatch("CREATE_SHEET", {
                sheetId,
                position: model.getters.getSheetIds().length,
                name: sheetName,
            });
            model.dispatch("ACTIVATE_SHEET", { sheetIdFrom, sheetIdTo: sheetId });
        }
        await subActionInitCallback(model, stores);
    };
}

initCallbackRegistry.add("workingFilePreprocessingAction", workingFilePreprocessingAction);
