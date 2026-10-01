import { registry } from "@web/core/registry";
import { POSAppointmentBookingGanttController } from "@pos_appointment/app/gantt_overrides/gantt_controller";
import { POSAppointmentBookingGanttRenderer } from "@pos_appointment/app/gantt_overrides/gantt_renderer";
import { AppointmentBookingGanttView } from "@appointment/views/gantt/gantt_view";
import { PosAppointmentControlPanel } from "@pos_appointment/override/web/control_panel";

export const posAppointmentBookingGanttView = {
    ...AppointmentBookingGanttView,
    Controller: POSAppointmentBookingGanttController,
    ControlPanel: PosAppointmentControlPanel,
    Renderer: POSAppointmentBookingGanttRenderer,
};

registry.category("views").add("pos_appointment_booking_gantt", posAppointmentBookingGanttView);
