import { patch } from "@web/core/utils/patch";
import { TimesheetTimerInlineForm } from "@timesheet_grid/components/timesheet_timer_inline_form/timesheet_timer_inline_form";

patch(TimesheetTimerInlineForm.prototype, {
    get activeFields() {
        const activeFields = super.activeFields;
        activeFields.helpdesk_ticket_id.placeholder = activeFields.helpdesk_ticket_id.string;
        return activeFields;
    },
});
