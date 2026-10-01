import { patch } from "@web/core/utils/patch";
import { TimesheetAssistantModel } from "@timesheet_grid/components/aw_timesheet/aw_timesheet_model";

patch(TimesheetAssistantModel.prototype, {
    _isSideActivityEvent(event) {
        if (event.keyEvent && event.type == "meeting") {
            return true;
        }
        return super._isSideActivityEvent(event);
    },
});
