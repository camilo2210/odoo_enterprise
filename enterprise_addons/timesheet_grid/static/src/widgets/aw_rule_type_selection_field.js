import { registry } from "@web/core/registry";
import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";
import { getAwRuleIcon } from "@timesheet_grid/utils/timesheets_assistant";

export class AwRuleTypeSelectionField extends SelectionField {
    static template = "timesheet_grid.AwRuleTypeSelectionField";
    getIcon = getAwRuleIcon;
}

registry.category("fields").add("aw_rule_type_selection", {
    ...selectionField,
    component: AwRuleTypeSelectionField,
    supportedTypes: ["selection"],
    additionalClasses: ["d-flex", "align-items-baseline"],
});
