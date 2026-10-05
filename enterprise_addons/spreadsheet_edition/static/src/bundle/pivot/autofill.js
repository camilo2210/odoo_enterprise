import * as spreadsheet from "@odoo/o-spreadsheet";
import { CompiledFormula } from "@odoo/o-spreadsheet";

import { Component, t, useProps } from "@odoo/owl";
import { containsReferences } from "@spreadsheet/helpers/helpers";
import {
    getPivotTooltipFormula,
    getPivotNextAutofillValue,
} from "@spreadsheet_edition/bundle/pivot/plugins/pivot_autofill_plugin";

const { autofillModifiersRegistry, autofillRulesRegistry } = spreadsheet.registries;
const { getNumberOfPivotFunctions } = spreadsheet.helpers;

function isOdooPivotFormula(compiledFormula, getters) {
    if (getNumberOfPivotFunctions(compiledFormula, getters) !== 1) {
        return false;
    }
    const { args } = getters.getFirstPivotFunction(getters.getActiveSheetId(), compiledFormula);
    const argPivotId = args.length > 0 && args[0]?.toString();
    if (!argPivotId) {
        return false;
    }
    const pivotId = getters.getPivotId(args[0].toString());
    if (!pivotId) {
        return false;
    }
    return getters.getPivotCoreDefinition(pivotId).type === "ODOO";
}

//--------------------------------------------------------------------------
// Autofill Component
//--------------------------------------------------------------------------
export class AutofillTooltip extends Component {
    static template = "spreadsheet_edition.AutofillTooltip";

    props = useProps({ content: t.array() });
}

//--------------------------------------------------------------------------
// Autofill Rules
//--------------------------------------------------------------------------

autofillRulesRegistry.add("autofill_pivot", {
    condition: (cell) =>
        cell &&
        cell.isFormula &&
        !containsReferences(cell) &&
        hasPivotFormula(cell.compiledFormula),
    generateRule: (cell, cells) => {
        const increment = cells.filter(
            (cell) => cell && cell.isFormula && hasPivotFormula(cell.compiledFormula)
        ).length;
        return { type: "PIVOT_UPDATER", increment, current: 0 };
    },
    sequence: 2,
});

//--------------------------------------------------------------------------
// Autofill Modifier
//--------------------------------------------------------------------------

autofillModifiersRegistry.add("PIVOT_UPDATER", {
    apply: (rule, data, getters, direction) => {
        if (!data.cell.isFormula || !isOdooPivotFormula(data.cell.compiledFormula, getters)) {
            data.cell.content = data.cell.compiledFormula.toFormulaString(getters);
            return { cellData: data.cell, tooltip: undefined };
        }
        rule.current += rule.increment;
        let isColumn;
        let steps;
        switch (direction) {
            case "up":
                isColumn = false;
                steps = -rule.current;
                break;
            case "down":
                isColumn = false;
                steps = rule.current;
                break;
            case "left":
                isColumn = true;
                steps = -rule.current;
                break;
            case "right":
                isColumn = true;
                steps = rule.current;
        }
        const content = getPivotNextAutofillValue(
            getters,
            data.cell.compiledFormula,
            isColumn,
            steps
        );
        let tooltip = {
            props: {
                content: data.content,
            },
        };
        if (content && content !== data.content) {
            const sheetId = data.cell.compiledFormula.sheetId;
            const compiledFormula = CompiledFormula.Compile(content, sheetId, getters);
            tooltip = {
                props: {
                    content: getPivotTooltipFormula(getters, compiledFormula, isColumn),
                },
                component: AutofillTooltip,
            };
        }
        if (!content) {
            tooltip = undefined;
        }
        return {
            cellData: {
                style: undefined,
                format: data.cell && data.cell.format,
                border: undefined,
                content,
            },
            tooltip,
        };
    },
});

const ALL_PIVOT_FUNCTIONS = ["PIVOT", "PIVOT.HEADER", "PIVOT.VALUE"];

export function hasPivotFormula(compiledFormula) {
    return ALL_PIVOT_FUNCTIONS.some((funcName) => compiledFormula.usesSymbol(funcName));
}
