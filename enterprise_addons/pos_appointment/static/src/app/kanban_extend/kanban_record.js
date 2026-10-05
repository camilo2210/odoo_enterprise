import { AppointmentCalendarEventKanbanRecord } from "@appointment/views/kanban/kanban_record";
import { POSAppointmentCalendarEventPopover } from "@pos_appointment/app/popover_extend/popover";
import { usePopover } from "@web/core/popover/popover_hook";

export class PosKanbanRecord extends AppointmentCalendarEventKanbanRecord {
    setup() {
        super.setup(...arguments);
        this.popover = usePopover(POSAppointmentCalendarEventPopover, { position: "bottom" });
    }
}
