import { deserializeDateTime } from "@web/core/l10n/dates";
import { localeCompare } from "@web/core/l10n/utils";
import { globalFieldMatchingRegistry } from "@spreadsheet/global_filters/helpers";

const { DateTime } = luxon;

export function formatToLocaleString(ISOdatetime, code) {
    return deserializeDateTime(ISOdatetime).setLocale(code).toLocaleString(DateTime.DATETIME_MED);
}

export function addToRegistryWithCleanup(cleanUpHook, registry, name, item) {
    registry.replace(name, item);
    cleanUpHook(() => {
        registry.remove(name);
    });
}

export function getDataSourcePriorityFields(getters, id, type) {
    switch (type) {
        case "list": {
            const definition = getters.getListDefinition(id);
            return definition.columns.map((col) => col.name);
        }
        case "pivot": {
            const definition = getters.getPivotCoreDefinition(id);
            return [...definition.columns, ...definition.rows].map((dim) => dim.fieldName);
        }
        case "chart": {
            const definition = getters.getChartDefinition(id);
            const groupBy = definition.dataSource.metaData?.groupBy ?? [];
            return groupBy.map((g) => g.split(":")[0]);
        }
    }
    return [];
}

export function filterDataSourceField(getters, dataSourceId, dataSourceType, field, path) {
    if (!field.searchable || field.type === "reference") {
        return false;
    }
    const matcher = globalFieldMatchingRegistry.get(dataSourceType);
    for (const filter of getters.getGlobalFilters()) {
        const fieldMatching = matcher.getFieldMatching(getters, dataSourceId, filter.id);
        if (fieldMatching?.chain === `${path ? `${path}.` : ""}${field.name}`) {
            return { isFieldAlreadyPresent: true };
        }
    }
    return true;
}

export function sortModelFieldSelectorFields(fields, priorityFields = []) {
    const prioritySet = new Set(priorityFields);
    return Object.keys(fields).sort((a, b) => {
        const aPriority = prioritySet.has(a);
        const bPriority = prioritySet.has(b);
        if (aPriority && bPriority) {
            return fields[a].string.localeCompare(fields[b].string);
        }
        if (aPriority !== bPriority) {
            return aPriority ? -1 : 1;
        }
        if (fields[a].relation && fields[b].relation) {
            return localeCompare(fields[a].string, fields[b].string);
        }
        if (fields[a].relation) {
            return 1;
        }
        if (fields[b].relation) {
            return -1;
        }
        return localeCompare(fields[a].string, fields[b].string);
    });
}

/** In the given formula, replace the content of the given function by the new content */
export function replaceFunctionInFormula(formula, functionName, newFunction) {
    if (newFunction.startsWith("=")) {
        newFunction = newFunction.slice(1);
    }
    const functionIndex = formula.indexOf(functionName);
    if (functionIndex === -1) {
        return formula;
    }
    const startParenthesisIndex = functionIndex + functionName.length;
    const endParenthesisIndex = getMatchingParenthesis(formula, startParenthesisIndex);
    if (endParenthesisIndex === -1) {
        return formula;
    }
    return formula.slice(0, functionIndex) + newFunction + formula.slice(endParenthesisIndex + 1);
}

function getMatchingParenthesis(str, openingIndex) {
    let counter = 1;
    for (let i = openingIndex + 1; i < str.length; i++) {
        if (str[i] === "(") {
            counter++;
        } else if (str[i] === ")") {
            counter--;
            if (counter === 0) {
                return i;
            }
        }
    }
    return -1; // No matching parenthesis found
}
