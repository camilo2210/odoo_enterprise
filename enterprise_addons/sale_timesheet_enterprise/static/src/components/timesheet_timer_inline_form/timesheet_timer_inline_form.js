import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { TimesheetTimerInlineForm } from "@timesheet_grid/components/timesheet_timer_inline_form/timesheet_timer_inline_form";

patch(TimesheetTimerInlineForm.prototype, {
    get activeFields() {
        const activeFields = super.activeFields;
        if (activeFields.is_billable) {
            activeFields.is_billable.field = {
                ...activeFields.is_billable.field,
                ...registry.category("fields").get("boolean_toggle"),
            };
        }
        return activeFields;
    },
});
