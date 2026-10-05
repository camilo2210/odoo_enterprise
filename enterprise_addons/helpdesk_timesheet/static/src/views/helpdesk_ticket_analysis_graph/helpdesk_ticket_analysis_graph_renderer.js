import { HelpdeskTicketAnalysisGraphRenderer } from "@helpdesk/views/helpdesk_ticket_analysis_graph/helpdesk_ticket_analysis_graph_renderer";
import { HelpdeskTimesheetTicketAnalysisRendererMixin } from "../helpdesk_timesheet_ticket_analysis_renderer_mixin";

export class HelpdeskTimesheetTicketAnalysisGraphRenderer extends HelpdeskTimesheetTicketAnalysisRendererMixin(
    HelpdeskTicketAnalysisGraphRenderer
) {}
