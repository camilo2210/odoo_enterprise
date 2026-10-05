import { KanbanHeader } from "@web/views/kanban/kanban_header";

export class AppointmentCalendarEventKanbanHeader extends KanbanHeader {
    static template = "appointment.AppointmentCalendarEventKanbanHeader";

    get totalColumnCapacity() {
        return this.props.group.list.records.reduce(
            (sum, record) =>
                sum + (record.data.appointment_type_manage_capacity ? record.data.total_capacity_reserved : 0), 0
        );
    }
}
