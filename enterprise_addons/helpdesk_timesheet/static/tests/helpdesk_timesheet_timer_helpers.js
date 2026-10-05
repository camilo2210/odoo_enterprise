import { setupTimesheetEnvironment } from "@timesheet_grid/../tests/timesheet_timer_helpers";
import { TimesheetInlineForm } from "@timesheet_grid/components/timesheet_inline_form/timesheet_inline_form";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";

export function setupHelpdeskTimesheetEnvironment() {
    const env = setupTimesheetEnvironment();

    patchWithCleanup(TimesheetInlineForm.prototype, {
        get activeFields() {
            const activeFields = super.activeFields;
            activeFields.project_id.onChange = true;
            return activeFields;
        },
    });

    return env;
}
