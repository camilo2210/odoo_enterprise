import { hasListFormula } from "@spreadsheet/list/list_helpers";
import { containsReferences } from "@spreadsheet/helpers/helpers";
import * as spreadsheet from "@odoo/o-spreadsheet";
import {
    getNextListValue,
    getTooltipListFormula,
} from "@spreadsheet_edition/bundle/list/plugins/list_autofill_plugin";

const { autofillModifiersRegistry, autofillRulesRegistry } = spreadsheet.registries;
const { CompiledFormula } = spreadsheet;

//--------------------------------------------------------------------------
// Autofill Rules
//--------------------------------------------------------------------------

autofillRulesRegistry.add("autofill_list", {
    condition: (cell) =>
        cell && cell.isFormula && hasListFormula(cell.compiledFormula) && !containsReferences(cell),
    generateRule: (cell, cells) => {
        const increment = cells.filter(
            (cell) => cell && cell.isFormula && hasListFormula(cell.compiledFormula)
        ).length;
        return { type: "LIST_UPDATER", increment, current: 0 };
    },
    sequence: 3,
});

//--------------------------------------------------------------------------
// Autofill Modifier
//--------------------------------------------------------------------------

autofillModifiersRegistry.add("LIST_UPDATER", {
    apply: (rule, data, getters, direction) => {
        if (!data.cell.isFormula || !hasListFormula(data.cell.compiledFormula)) {
            throw new Error("Trying to list autofill on a non-list cell");
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
        const content = getNextListValue(getters, data.cell.compiledFormula, isColumn, steps);
        let tooltip = {
            props: {
                content,
            },
        };
        if (content && content !== data.content) {
            const sheetId = data.cell.compiledFormula.sheetId;
            const compiledFormula = CompiledFormula.Compile(content, sheetId, getters);
            tooltip = {
                props: {
                    content: getTooltipListFormula(getters, compiledFormula, isColumn),
                },
            };
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
