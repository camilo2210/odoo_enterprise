import { AppointmentCalendarEventKanbanHeader } from "@appointment/views/kanban/kanban_header";

export class PosKanbanHeader extends AppointmentCalendarEventKanbanHeader {
    get totalColumnCapacity() {
        return this.props.group.list.records.reduce(
            (sum, record) =>
                sum + (record.data.waiting_list_capacity || record.data.total_capacity_reserved),
            0
        );
    }
}
