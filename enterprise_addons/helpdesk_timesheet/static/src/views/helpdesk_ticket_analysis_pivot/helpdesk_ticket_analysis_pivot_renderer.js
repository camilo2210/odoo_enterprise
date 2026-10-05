import { HelpdeskTicketAnalysisPivotRenderer } from "@helpdesk/views/helpdesk_ticket_analysis_pivot/helpdesk_ticket_analysis_pivot_renderer";
import { HelpdeskTimesheetTicketAnalysisRendererMixin } from "../helpdesk_timesheet_ticket_analysis_renderer_mixin";

export class HelpdeskTimesheetTicketAnalysisPivotRenderer extends HelpdeskTimesheetTicketAnalysisRendererMixin(
    HelpdeskTicketAnalysisPivotRenderer
) {}
