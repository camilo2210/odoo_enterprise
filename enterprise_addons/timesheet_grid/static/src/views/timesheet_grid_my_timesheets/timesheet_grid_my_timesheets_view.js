import { registry } from "@web/core/registry";

import { timesheetGridView } from "../timesheet_grid/timesheet_grid_view";
import { TimesheetGridMyTimesheetsController } from "./timesheet_grid_my_timesheets_controller";
import { TimesheetGridMyTimesheetsModel } from "./timesheet_grid_my_timesheets_model";
import { TimesheetGridMyTimesheetsRenderer } from "./timesheet_grid_my_timesheets_renderer";

export const myTimesheetsGridView = {
    ...timesheetGridView,
    Controller: TimesheetGridMyTimesheetsController,
    Model: TimesheetGridMyTimesheetsModel,
    Renderer: TimesheetGridMyTimesheetsRenderer,
};

registry.category("views").add("timesheet_grid_my_timesheets", myTimesheetsGridView);
