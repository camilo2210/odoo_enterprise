import { _t } from "@web/core/l10n/translation";
import { helpers } from "@odoo/o-spreadsheet";
import { domainHasNoRecordAtThisPosition } from "@spreadsheet/pivot/pivot_helpers";
import { replaceFunctionInFormula } from "@spreadsheet_edition/bundle/helpers/misc";

const {
    getNumberOfPivotFunctions,
    isDateOrDatetimeField,
    pivotTimeAdapter,
    createPivotFormula,
    domainToColRowDomain,
} = helpers;

/**
 * @typedef {import("@odoo/o-spreadsheet").SpreadsheetPivotTable} SpreadsheetPivotTable
 * @typedef {import("@spreadsheet").OdooPivotDefinition} OdooPivotDefinition
 * @typedef {import("@spreadsheet/pivot/odoo_pivot").OdooPivot} OdooPivot
 * @typedef {import("@spreadsheet/pivot/odoo_pivot").PivotDomain} PivotDomain
 */

/**
 * @typedef CurrentElement
 * @property {Array<string>} cols
 * @property {Array<string>} rows
 *
 * @typedef TooltipFormula
 * @property {string} value
 *
 * @typedef GroupByDate
 * @property {boolean} isDate
 * @property {string|undefined} group
 */

const WILDCARD = Symbol("*");

/**
 * Get the next value to autofill of a pivot function
 *
 * @param {string} formula Pivot formula
 * @param {boolean} isColumn True if autofill is LEFT/RIGHT, false otherwise
 * @param {number} increment number of steps
 *
 * @returns {string}
 */
export function getPivotNextAutofillValue(getters, compiledFormula, isColumn, increment) {
    const formula = compiledFormula.toFormulaString(getters);
    if (getNumberOfPivotFunctions(compiledFormula, getters) !== 1) {
        return formula;
    }
    const { functionName, args } = getters.getFirstPivotFunction(
        compiledFormula.sheetId,
        compiledFormula
    );
    if (args.some((arg) => arg === undefined)) {
        return formula;
    }
    const pivotId = getters.getPivotId(args[0]);
    if (!pivotId || !["PIVOT.VALUE", "PIVOT.HEADER"].includes(functionName)) {
        return formula;
    }
    const dataSource = getters.getPivot(pivotId);
    const definition = dataSource.definition;
    for (let i = args.length - 1; i > 0; i--) {
        const fieldName = args[i];
        if (
            typeof fieldName === "string" &&
            fieldName.startsWith("#") &&
            ((isColumn && _isColumnGroupBy(dataSource, definition, fieldName)) ||
                (!isColumn && _isRowGroupBy(dataSource, definition, fieldName)))
        ) {
            args[i + 1] = parseInt(args[i + 1], 10) + increment;
            if (args[i + 1] < 0) {
                return formula;
            }
            if (functionName === "PIVOT.VALUE") {
                const [formulaId, measure, ...domain] = args;
                const pivotCell = {
                    type: "VALUE",
                    measure,
                    domain: _toPivotDomainWithPositional(dataSource, domain),
                };
                const newPivotFunction = createPivotFormula(formulaId, pivotCell);
                return replaceFunctionInFormula(formula, functionName, newPivotFunction);
            } else if (functionName === "PIVOT.HEADER") {
                const [formulaId, ...domain] = args;
                const pivotCell = {
                    type: "HEADER",
                    domain: _toPivotDomainWithPositional(dataSource, domain),
                };
                const newPivotFunction = createPivotFormula(formulaId, pivotCell);
                return replaceFunctionInFormula(formula, functionName, newPivotFunction);
            }
            return formula;
        }
    }

    const dimension = isColumn ? "COL" : "ROW";
    const newPivotFunction = _autoFillPivot(
        getters,
        pivotId,
        args,
        functionName,
        dimension,
        increment
    );
    return newPivotFunction
        ? replaceFunctionInFormula(formula, functionName, newPivotFunction)
        : "";
}

/**
 * Autofill non-positional pivot formulas.
 *
 * The desired behaviour is that from a single pivot formula cell, we can re-create the whole pivot by auto-filling
 * in all directions.
 *
 * To do so, from the autofill origin cell, we find the corresponding pivot cell in the `pivotCells` structure, then
 * we move in the desired direction to find the target pivot cell.
 */
function _autoFillPivot(getters, pivotId, args, fnName, dimension, increment) {
    const pivot = getters.getPivot(pivotId);
    const table = pivot.getExpandedTableStructure();
    const pivotCells = table.getPivotCells();

    const { formulaId, measure, domain } = _parsePivotFunctionArgs(pivot, fnName, args);
    if (!formulaId || !domain) {
        return "";
    }

    if (_shouldAutofillIncrementDates(pivot, domain, dimension)) {
        const targetCell = _autofillByIncrementingDates(
            pivot,
            domain,
            dimension,
            fnName,
            measure,
            increment
        );
        return targetCell ? createPivotFormula(formulaId, targetCell) : "";
    }

    // The autofill origin cell might not exist in the pivotCells structure (eg. autofilling from a date header not
    // present in the pivot data). But with one groupBy, we don't need to find an exact match, we only need to find
    // a cell with the same domain in the autofill dimension, and any value in the other dimension.
    const { colDomain, rowDomain } = domainToColRowDomain(pivot, domain);
    let searchDomain = domain;
    if (dimension === "ROW" && pivot.definition.columns.length === 1) {
        searchDomain = [...rowDomain, ...colDomain.map((node) => ({ ...node, value: WILDCARD }))];
    } else if (dimension === "COL" && pivot.definition.rows.length === 1) {
        searchDomain = [...rowDomain.map((node) => ({ ...node, value: WILDCARD })), ...colDomain];
    }
    const originCell = _findPivotCell(pivotCells, searchDomain, measure, dimension, fnName);
    if (!originCell) {
        return "";
    }

    const targetCol = dimension === "COL" ? originCell.col + increment : originCell.col;
    const targetRow = dimension === "COL" ? originCell.row : originCell.row + increment;
    const targetCell = pivotCells[targetCol]?.[targetRow];
    if (!targetCell || targetCell.type === "EMPTY") {
        return "";
    }

    // If we didn't search for an exact domain match, we need to reconstruct the full domain for the target cell
    let resultDomain = targetCell.domain;
    if (dimension === "ROW" && domain !== searchDomain) {
        resultDomain = [...domainToColRowDomain(pivot, targetCell.domain).rowDomain, ...colDomain];
    } else if (dimension === "COL" && domain !== searchDomain) {
        resultDomain = [...rowDomain, ...domainToColRowDomain(pivot, targetCell.domain).colDomain];
    }

    const domainWithPositionals = _addBackPositionalArgumentsToDomain(args, resultDomain);
    const newPivotCell = { ...targetCell, domain: domainWithPositionals };

    return createPivotFormula(formulaId, newPivotCell);
}

function _autofillByIncrementingDates(pivot, domain, dimension, functionName, measure, increment) {
    if (domain.length === 0) {
        return undefined;
    }

    const groupBys = dimension === "COL" ? pivot.definition.columns : pivot.definition.rows;
    const granularity = groupBys[0].granularity || "month";

    const dimensionDomain =
        dimension === "COL"
            ? domainToColRowDomain(pivot, domain).colDomain
            : domainToColRowDomain(pivot, domain).rowDomain;

    const newValue = _incrementDate(dimensionDomain[0].value, granularity, increment);
    const nodeIndexInDomain = domain.findIndex((node) => node === dimensionDomain[0]);
    if (nodeIndexInDomain === -1 || newValue === undefined) {
        return undefined;
    }
    const newDomain = [...domain];
    newDomain[nodeIndexInDomain] = { ...newDomain[nodeIndexInDomain], value: newValue };

    if (functionName === "PIVOT.VALUE") {
        return { type: "VALUE", domain: newDomain, measure };
    } else if (measure) {
        return { type: "MEASURE_HEADER", domain: newDomain, measure };
    }
    return { type: "HEADER", domain: newDomain, dimension };
}

/**
 * We have a special autofill behavior for date fields, where instead of trying to re-create the
 * original pivot from the pivot cell, we just increment the date value in the domain.
 *
 * This only works if:
 *  - The pivot definition only has a single date groupBy in the autofill dimension
 *  - The current auto-filled cell has a date groupBy in the autofill dimension
 *
 */
function _shouldAutofillIncrementDates(pivot, domain, dimension) {
    const groupBys = dimension === "COL" ? pivot.definition.columns : pivot.definition.rows;
    if (groupBys.length !== 1 || !isDateOrDatetimeField(groupBys[0])) {
        return false;
    }

    const dimensionDomain =
        dimension === "COL"
            ? domainToColRowDomain(pivot, domain).colDomain
            : domainToColRowDomain(pivot, domain).rowDomain;

    return dimensionDomain.some((node) => ["date", "datetime"].includes(node.type));
}

function _parsePivotFunctionArgs(pivot, functionName, args) {
    try {
        if (functionName === "PIVOT.VALUE") {
            const [formulaId, measure, ...domainArgs] = args;
            const domain = pivot.parseArgsToPivotDomain(domainArgs);
            return { formulaId, measure, domain };
        } else if (functionName === "PIVOT.HEADER") {
            const [formulaId, ...domainArgs] = args;
            const domain = pivot.parseArgsToPivotDomain(domainArgs);
            const lastNode = domain.at(-1);
            let measure = undefined;
            if (lastNode?.field === "measure") {
                measure = lastNode.value;
                domain.pop();
            }
            return { formulaId, measure, domain };
        }
    } catch {
        // Parsing to a pivot domain will throw if the formula arguments are invalid
        return {};
    }
}

/** Find the pivot cell matching the pivot formula of the autofill origin cell */
function _findPivotCell(pivotCells, domain, measure, autofillDimension, functionName) {
    // There's two cells that have the same domain: the two pivot headers for the grand total of rows and columns
    // In that case, we determine which one to pick based on the autofill direction
    // If we're autofilling the columns, we want to autofill from the row grand total header & vice versa
    let searchedDimension = undefined;
    if (domain.length === 0 && !measure) {
        searchedDimension = autofillDimension === "COL" ? "ROW" : "COL";
    }

    for (let col = 0; col < pivotCells.length; col++) {
        for (let row = 0; row < pivotCells[col].length; row++) {
            const cell = pivotCells[col][row];
            if (
                (functionName === "PIVOT.VALUE" && cell.type !== "VALUE") ||
                cell.type === "EMPTY"
            ) {
                continue;
            }
            if (areDomainsEqual(cell.domain, domain) && cell.measure === measure) {
                if (searchedDimension && cell.dimension !== searchedDimension) {
                    continue;
                }
                return { row, col, cell };
            }
        }
    }
}

/**
 * When we parse the arguments of the function to a domain, we lose the positional information arguments, and the
 * values of the domain nodes become wrong (eg. `"#country_id", 1"` might become
 * `{ field: "country_id", value: "__NO_RECORD_AT_THIS_POSITION__"}` once parsed).
 *
 * This is not a problem during the autofill, since we ignore the values of the domain for the fields not in the
 * direction of the autofill. But we need to add them back to the final result.
 */
function _addBackPositionalArgumentsToDomain(functionArgs, domain) {
    const domainWithPositional = [...domain];
    for (let i = 1; i < functionArgs.length - 1; i++) {
        if (typeof functionArgs[i] !== "string" || !functionArgs[i].startsWith("#")) {
            continue;
        }
        const field = functionArgs[i].slice(1);
        const positionalValue = functionArgs[i + 1];
        const indexInDomain = domain.findIndex((node) => node.field === field);
        if (indexInDomain !== -1) {
            domainWithPositional.splice(indexInDomain, 1, {
                ...domain[indexInDomain],
                field: functionArgs[i],
                value: positionalValue,
            });
        }
    }
    return domainWithPositional;
}

/**
 * Check if two pivot domains are equal. This accepts wildcards in the domain values.
 */
function areDomainsEqual(domain1, domain2) {
    if (!domain1 || !domain2) {
        return false;
    } else if (domain1.length !== domain2.length) {
        return false;
    }
    for (let i = 0; i < domain1.length; i++) {
        if (domain1[i].field !== domain2[i].field || domain1[i].type !== domain2[i].type) {
            return false;
        }
        if (domain1[i].value === WILDCARD || domain2[i].value === WILDCARD) {
            continue;
        }
        if (domain1[i].value !== domain2[i].value) {
            return false;
        }
    }
    return true;
}

/**
 * Compute the tooltip to display from a Pivot formula
 *
 * @param {string} formula Pivot formula
 * @param {boolean} isColumn True if the direction is left/right, false
 *                           otherwise
 *
 * @returns {Array<TooltipFormula>}
 */
export function getPivotTooltipFormula(getters, compiledFormula, isColumn) {
    if (getNumberOfPivotFunctions(compiledFormula, getters) !== 1) {
        return [];
    }
    const { functionName, args } = getters.getFirstPivotFunction(
        getters.getActiveSheetId(),
        compiledFormula
    );
    const pivotId = getters.getPivotId(args[0]);
    if (!pivotId) {
        return [{ title: _t("Missing pivot"), value: _t("Missing pivot #%s", args[0]) }];
    }
    if (functionName === "PIVOT.VALUE") {
        const dataSource = getters.getPivot(pivotId);
        const definition = dataSource.definition;
        return _tooltipFormatPivot(args, isColumn, dataSource, definition);
    } else if (functionName === "PIVOT.HEADER") {
        const dataSource = getters.getPivot(pivotId);
        return _tooltipFormatPivotHeader(args, dataSource);
    }
    return [];
}

/**
 * Increment a date with a given increment and interval (group)
 *
 * @param {string} date
 * @param {string} group (day, week, month, ...)
 * @param {number} increment
 *
 * @private
 * @returns {string}
 */
function _incrementDate(date, group, increment) {
    const adapter = pivotTimeAdapter(group);
    const value = adapter.normalizeFunctionValue(date);
    return adapter.increment(value, increment);
}

/**
 * Get the tooltip for a pivot formula
 *
 * @param {string} pivotId Id of the pivot
 * @param {Array<string>} args
 * @param {boolean} isColumn True if the direction is left/right, false
 *                           otherwise
 * @param {OdooPivot} dataSource
 * @param {OdooPivotDefinition} definition
 *
 * @private
 *
 * @returns {Array<TooltipFormula>}
 */
function _tooltipFormatPivot(args, isColumn, dataSource, definition) {
    const tooltips = [];
    const domain = args.slice(2);
    for (let i = 0; i < domain.length; i += 2) {
        if (
            (isColumn && _isColumnGroupBy(dataSource, definition, domain[i])) ||
            (!isColumn && _isRowGroupBy(dataSource, definition, domain[i]))
        ) {
            tooltips.push(_tooltipHeader(dataSource, domain.slice(0, i + 2)));
        }
    }
    if (definition.measures.length !== 1 && isColumn) {
        const measure = args[1];
        tooltips.push({
            value: dataSource.getMeasure(measure).displayName,
        });
    }
    if (!tooltips.length) {
        tooltips.push({
            value: _t("Total"),
        });
    }
    return tooltips;
}
/**
 * Get the tooltip for a pivot header formula
 *
 * @param {string} pivotId
 * @param {Array<string>} args
 * @param {OdooPivot} dataSource
 *
 * @private
 *
 * @returns {Array<TooltipFormula>}
 */
function _tooltipFormatPivotHeader(args, dataSource) {
    const tooltips = [];
    const domain = args.slice(1).map((value) => ({ value }));
    if (domain.length === 0) {
        return [{ value: _t("Total") }];
    }

    for (let i = 0; i < domain.length; i += 2) {
        tooltips.push(_tooltipHeader(dataSource, domain.slice(0, i + 2)));
    }
    return tooltips;
}

function _tooltipHeader(dataSource, domain) {
    const subDomain = dataSource.parseArgsToPivotDomain(domain);
    if (!domainHasNoRecordAtThisPosition(subDomain)) {
        const formattedValue = _getPivotHeaderFormattedValue(dataSource, subDomain);
        return { value: formattedValue };
    } else {
        return { value: "" };
    }
}

function _getPivotHeaderFormattedValue(dataSource, domain) {
    try {
        return dataSource.getPivotHeaderFormattedValue(domain);
    } catch {
        return _t("Unknown");
    }
}

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

function _toPivotDomainWithPositional(pivot, args) {
    const domain = [];
    for (let i = 0; i < args.length - 1; i += 2) {
        const fullName = args[i];
        const { field, isPositional } = pivot.parseGroupField(fullName);
        domain.push({
            field: fullName,
            value: args[i + 1],
            type: isPositional ? "integer" : field.type,
        });
    }
    return domain;
}

/**
 * @param {OdooPivot} dataSource
 * @param {OdooPivotDefinition} definition
 * @param {string} fieldName
 * @returns {boolean}
 */
function _isColumnGroupBy(dataSource, definition, fieldName) {
    const name = dataSource.parseGroupField(fieldName).field.name;
    return definition.columns.map((col) => col.fieldName).includes(name);
}

/**
 * @param {OdooPivot} dataSource
 * @param {OdooPivotDefinition} definition
 * @param {string} fieldName
 * @returns {boolean}
 */
function _isRowGroupBy(dataSource, definition, fieldName) {
    const name = dataSource.parseGroupField(fieldName).field.name;
    return definition.rows.map((row) => row.fieldName).includes(name);
}
