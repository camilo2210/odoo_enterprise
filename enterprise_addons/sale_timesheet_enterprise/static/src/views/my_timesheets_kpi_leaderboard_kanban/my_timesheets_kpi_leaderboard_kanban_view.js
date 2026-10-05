import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

import {
    TimesheetKpiLeaderboardHeader
} from "../../components/timesheet_kpi_leaderboard_header/timesheet_kpi_leaderboard_header";


export class MyTimesheetsKpiLeaderboardKanbanModel extends kanbanView.Model {
    static withCache = false;
}

export class MyTimesheetsKpiLeaderboardKanbanRenderer extends KanbanRenderer {
    static template = "sale_timesheet_enterprise.MyTimesheetsKpiLeaderboardKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        TimesheetKpiLeaderboardHeader: TimesheetKpiLeaderboardHeader,
    };
}

export const myTimesheetsKpiLeaderboardKanbanView = {
    ...kanbanView,
    Model: MyTimesheetsKpiLeaderboardKanbanModel,
    Renderer: MyTimesheetsKpiLeaderboardKanbanRenderer,
};

registry.category("views").add("my_timesheets_kpi_leaderboard_kanban", myTimesheetsKpiLeaderboardKanbanView);
