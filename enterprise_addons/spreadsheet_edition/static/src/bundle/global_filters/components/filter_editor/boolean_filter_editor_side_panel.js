/** @ts-check */

import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { getOperatorLabel } from "@web/core/tree_editor/tree_editor_operator_editor";
import { components } from "@odoo/o-spreadsheet";

const { Select } = components;

export class BooleanFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.BooleanFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        FilterEditorFieldMatching,
        Select,
    };

    get type() {
        return "boolean";
    }

    updateBooleanDefaultValue(value) {
        if (value === "") {
            this.store.update({ defaultValue: undefined });
        } else {
            this.store.update({ defaultValue: { operator: value } });
        }
    }

    get operatorOptions() {
        return [
            { value: "", label: "" },
            { value: "set", label: getOperatorLabel("set") },
            { value: "not set", label: getOperatorLabel("not set") },
        ];
    }
}
