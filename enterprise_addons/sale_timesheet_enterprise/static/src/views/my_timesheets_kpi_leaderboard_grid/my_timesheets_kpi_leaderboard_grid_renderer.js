import { patch } from "@web/core/utils/patch";

import {
    TimesheetKpiLeaderboardHeader
} from "../../components/timesheet_kpi_leaderboard_header/timesheet_kpi_leaderboard_header";
import { TimesheetGridMyTimesheetsRenderer } from "@timesheet_grid/views/timesheet_grid_my_timesheets/timesheet_grid_my_timesheets_renderer";

patch(TimesheetGridMyTimesheetsRenderer, {
    components: {
        ...TimesheetGridMyTimesheetsRenderer.components,
        TimesheetKpiLeaderboardHeader: TimesheetKpiLeaderboardHeader,
    },
    template: "sale_timesheet_enterprise.MyTimesheetsKpiLeaderboardGridRenderer",
});
