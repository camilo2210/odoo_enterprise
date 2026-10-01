import { registry } from "@web/core/registry";
import {
    SelectionField,
    selection_field as selectionField,
} from "@web/views/fields/selection/selection_field";

export class ReportTypeSelectionField extends SelectionField {
    get choices() {
        const selection = this.props.record.fields[this.props.name].selection.map(
            ([value, label]) => ({ value, label })
        );
        if (
            ["vsme_basic", "vsme_advanced"].includes(this.props.record.context?.default_report_type)
        ) {
            const indexToRemove = selection.findIndex((item) => item.value === "csrd");
            if (indexToRemove !== -1) {
                selection.splice(indexToRemove, 1);
            }
        } else if (this.props.record.context?.default_report_type === "csrd") {
            let indexToRemove = selection.findIndex((item) => item.value === "vsme_basic");
            if (indexToRemove !== -1) {
                selection.splice(indexToRemove, 1);
            }
            indexToRemove = selection.findIndex((item) => item.value === "vsme_advanced");
            if (indexToRemove !== -1) {
                selection.splice(indexToRemove, 1);
            }
        }
        return selection;
    }
}

registry.category("fields").add("report_type_selection", {
    ...selectionField,
    component: ReportTypeSelectionField,
});
