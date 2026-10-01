import { registry } from "@web/core/registry";

import { timesheetGridView } from "../timesheet_grid/timesheet_grid_view";
import { TimesheetGridMyTimesheetsModel } from "./timesheet_grid_my_timesheets_model";
import { TimesheetGridMyTimesheetsRenderer } from "./timesheet_grid_my_timesheets_renderer";

export const myTimesheetsGridView = {
    ...timesheetGridView,
    Model: TimesheetGridMyTimesheetsModel,
    Renderer: TimesheetGridMyTimesheetsRenderer,
};

registry.category("views").add("timesheet_grid_my_timesheets", myTimesheetsGridView);
