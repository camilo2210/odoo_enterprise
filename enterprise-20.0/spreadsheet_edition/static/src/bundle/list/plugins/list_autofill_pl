import { _t } from "@web/core/l10n/translation";
import { astToFormula } from "@odoo/o-spreadsheet";
import { getFirstListFunction, hasListFormula } from "@spreadsheet/list/list_helpers";
import { replaceFunctionInFormula } from "@spreadsheet_edition/bundle/helpers/misc";

/**
 * Get the next value to autofill of a list function
 *
 * @param {string} formula List formula
 * @param {boolean} isColumn True if autofill is LEFT/RIGHT, false otherwise
 * @param {number} increment number of steps
 *
 * @returns Autofilled value
 */
export function getNextListValue(getters, compiledFormula, isColumn, increment) {
    if (!hasListFormula(compiledFormula)) {
        return formula;
    }
    const { functionName, args } = getFirstListFunction(compiledFormula, getters);
    const evaluatedArgs = args
        .map(astToFormula)
        .map((arg) => getters.evaluateFormula(compiledFormula.sheetId, arg));
    const listId = evaluatedArgs[0];
    const formula = compiledFormula.toFormulaString(getters);
    if (!getters.isExistingList(listId)) {
        return formula;
    }
    const columns = getters.getListDefinition(listId).columns;
    if (functionName === "ODOO.LIST.VALUE") {
        const position = parseInt(evaluatedArgs[1], 10);
        const field = evaluatedArgs[2];
        if (isColumn) {
            /** Change the field */
            const index = columns.findIndex((col) => col.name === field) + increment;
            if (index < 0 || index >= columns.length) {
                return "";
            }
            const newListFormula = _getListFunction(listId, position, columns[index].name);
            return replaceFunctionInFormula(formula, functionName, newListFormula);
        } else {
            /** Change the position */
            const nextPosition = position + increment;
            if (nextPosition === 0) {
                const newListFormula = _getListHeaderFunction(listId, field);
                return replaceFunctionInFormula(formula, functionName, newListFormula);
            }
            if (nextPosition < 0) {
                return "";
            }
            const newListFormula = _getListFunction(listId, nextPosition, field);
            return replaceFunctionInFormula(formula, functionName, newListFormula);
        }
    }
    if (functionName === "ODOO.LIST.HEADER") {
        const field = evaluatedArgs[1];
        if (isColumn) {
            /** Change the field */
            const index = columns.findIndex((col) => col.name === field) + increment;
            if (index < 0 || index >= columns.length) {
                return "";
            }
            const newListFormula = _getListHeaderFunction(listId, columns[index].name);
            return replaceFunctionInFormula(formula, functionName, newListFormula);
        } else {
            /** If down, set position */
            if (increment > 0) {
                const newListFormula = _getListFunction(listId, increment, field);
                return replaceFunctionInFormula(formula, functionName, newListFormula);
            }
            return "";
        }
    }
    return formula;
}

/**
 * Compute the tooltip to display from a Pivot formula
 *
 * @param {string} formula Pivot formula
 * @param {boolean} isColumn True if the direction is left/right, false
 *                           otherwise
 */
export function getTooltipListFormula(getters, compiledFormula, isColumn) {
    if (!compiledFormula) {
        return "";
    }
    const { functionName, args } = getFirstListFunction(compiledFormula);
    const evaluatedArgs = args
        .map(astToFormula)
        .map((arg) => getters.evaluateFormula(compiledFormula.sheetId, arg));
    const listId = evaluatedArgs[0];
    if (!getters.isExistingList(listId)) {
        return _t("Missing list #%s", listId);
    }
    if (!getters.getListDataSource(listId).isReady()) {
        return _t("Loading...");
    }
    if (isColumn || functionName === "ODOO.LIST.HEADER") {
        const fieldName = functionName === "ODOO.LIST.VALUE" ? evaluatedArgs[2] : evaluatedArgs[1];
        return getters.getListDataSource(listId).getListHeaderValue(fieldName).value;
    }
    return _t("Record #%(record_number)s", { record_number: evaluatedArgs[1] });
}

function _getListFunction(listId, position, field) {
    return `=ODOO.LIST.VALUE(${listId},${position},"${field}")`;
}

function _getListHeaderFunction(listId, field) {
    return `=ODOO.LIST.HEADER(${listId},"${field}")`;
}
