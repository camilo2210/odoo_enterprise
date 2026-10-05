import { registry } from "@web/core/registry";
import { pivotView } from "@web/views/pivot/pivot_view";
import { HelpdeskTimesheetTicketAnalysisPivotRenderer } from "./helpdesk_ticket_analysis_pivot_renderer";

export const helpdeskTimesheetTicketAnalysisPivotView = {
    ...pivotView,
    Renderer: HelpdeskTimesheetTicketAnalysisPivotRenderer,
};

registry
    .category("views")
    .add("hr_timesheet_helpdesk_ticket_analysis_pivot", helpdeskTimesheetTicketAnalysisPivotView);
