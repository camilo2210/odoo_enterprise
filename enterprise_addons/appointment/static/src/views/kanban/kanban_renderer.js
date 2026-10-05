import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { AppointmentCalendarEventKanbanHeader } from "@appointment/views/kanban/kanban_header";
import { AppointmentCalendarEventKanbanRecord } from "@appointment/views/kanban/kanban_record";
import { AppointmentTypeActionHelper } from "@appointment/components/appointment_type_action_helper/appointment_type_action_helper";

export class AppointmentCalendarEventKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: AppointmentCalendarEventKanbanHeader,
        KanbanRecord: AppointmentCalendarEventKanbanRecord,
    };
}

export class AppointmentTypeKanbanRenderer extends KanbanRenderer {
    static template = "appointment.AppointmentTypeKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        AppointmentTypeActionHelper,
    };
}
