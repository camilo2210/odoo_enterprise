import { AppointmentBookingGanttRenderer } from "@appointment/views/gantt/gantt_renderer";
import { POSAppointmentGanttPopover } from "./gantt_popover";

export class POSAppointmentBookingGanttRenderer extends AppointmentBookingGanttRenderer {
    static pillTemplate = "pos_gantt.GanttRenderer.Pill";
    static rowHeaderTemplate = "pos_gantt.GanttRenderer.RowHeader";
    static components = {
        ...AppointmentBookingGanttRenderer.components,
        Popover: POSAppointmentGanttPopover,
    };

    setup() {
        super.setup(...arguments);
        this.model.metaData.scale.groupHeaderFormatter = (date, env) =>
            luxon.DateTime.fromISO(date, env.locale).toFormat("EEEE, MMMM d, yyyy");
    }

    getOnClickAddLeaveContext() {
        return {
            ...super.getOnClickAddLeaveContext(),
            default_appointment_type_id:
                this.env.searchModel?._context["default_appointment_type_id"],
        };
    }
}
