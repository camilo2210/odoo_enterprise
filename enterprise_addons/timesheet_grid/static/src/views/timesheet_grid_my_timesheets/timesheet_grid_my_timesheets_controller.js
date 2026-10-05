import { TimesheetGridController } from "../timesheet_grid/timesheet_grid_controller";

export class TimesheetGridMyTimesheetsController extends TimesheetGridController {

    createRecord(params) {
        super.createRecord({
            ...(params || {}),
            expandedFormRef: "hr_timesheet.hr_timesheet_line_form",
        });
    }

}
