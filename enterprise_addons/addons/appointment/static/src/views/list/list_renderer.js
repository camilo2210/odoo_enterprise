import { AppointmentTypeActionHelper } from "@appointment/components/appointment_type_action_helper/appointment_type_action_helper";
import { ListRenderer } from "@web/views/list/list_renderer";

export class AppointmentTypeListRenderer extends ListRenderer {
    static template = "appointment.AppointmentTypeListRenderer";
    static components = {
        ...ListRenderer.components,
        AppointmentTypeActionHelper,
    };
}
