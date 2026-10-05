import { Component, t, useProps } from "@odoo/owl";
import { getFilterTypeOperators } from "@spreadsheet/global_filters/helpers";
import { getOperatorLabel } from "@web/core/tree_editor/tree_editor_operator_editor";
import { FilterValue } from "@spreadsheet/global_filters/components/filter_value/filter_value";
import { components } from "@odoo/o-spreadsheet";

const { Select } = components;

/**
 * Component that renders the interactive part of a global filter,
 * combining the operator selector and value input.
 * Encapsulates both controls into a single reusable unit.
 */
export class GlobalFilterInput extends Component {
    static template = "spreadsheet_edition.GlobalFilterInput";
    static components = { FilterValue, Select };

    props = useProps({
        filter: t.object(),
        setGlobalFilterValue: t.function(),
        updateOperator: t.function().optional(),
        globalFilterValue: t.object().optional(),
        searchableParentRelations: t.object().optional(),
        rangesOfAllowedValues: t.array().optional(),
    });

    get operators() {
        const { filter, searchableParentRelations } = this.props;
        let operators = getFilterTypeOperators(filter.type);
        if (filter.type === "relation" && !searchableParentRelations?.[filter.modelName]) {
            operators = operators.filter((op) => op !== "child_of");
        }
        return filter.type === "boolean" ? [undefined, ...operators] : operators;
    }

    get globalFilterValue() {
        return this.props.globalFilterValue;
    }

    get operatorOptions() {
        return this.operators.map((operator) => ({
            value: operator || "",
            label: operator ? getOperatorLabel(operator) : "",
        }));
    }
}
