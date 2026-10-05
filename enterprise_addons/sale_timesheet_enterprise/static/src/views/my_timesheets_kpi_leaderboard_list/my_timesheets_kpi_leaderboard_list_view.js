import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";

import {
    TimesheetKpiLeaderboardHeader
} from "../../components/timesheet_kpi_leaderboard_header/timesheet_kpi_leaderboard_header";


export class MyTimesheetsKpiLeaderboardListModel extends listView.Model {
    static withCache = false;
}

export class MyTimesheetsKpiLeaderboardListRenderer extends ListRenderer {
    static template = "sale_timesheet_enterprise.MyTimesheetsKpiLeaderboardListRenderer";
    static components = {
        ...ListRenderer.components,
        TimesheetKpiLeaderboardHeader: TimesheetKpiLeaderboardHeader,
    };
}

export const myTimesheetsKpiLeaderboardListView = {
    ...listView,
    Model: MyTimesheetsKpiLeaderboardListModel,
    Renderer: MyTimesheetsKpiLeaderboardListRenderer,
};

registry.category("views").add("my_timesheets_kpi_leaderboard_list", myTimesheetsKpiLeaderboardListView);
