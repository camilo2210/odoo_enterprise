import { AppointmentGanttPopover } from "@appointment/views/gantt/gantt_popover";
import { POSAppointmentCalendarEventPopover } from "@pos_appointment/app/popover_extend/popover";

export class POSAppointmentGanttPopover extends AppointmentGanttPopover {
    static template = "pos_appointment.POSAppointmentGanttPopover";
    static components = { POSAppointmentCalendarEventPopover };
}
