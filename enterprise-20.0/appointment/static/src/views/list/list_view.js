import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { AppointmentBookingListController, AppointmentTypeListController} from "@appointment/views/list/list_controller";
import { AppointmentTypeListRenderer} from "@appointment/views/list/list_renderer";

export const AppointmentBookingListView = {
    ...listView,
    Controller: AppointmentBookingListController,
    buttonTemplate: 'appointment.List.Buttons',
};

registry.category("views").add("appointment_booking_list", AppointmentBookingListView);

export const AppointmentTypeListView = {
    ...listView,
    Controller: AppointmentTypeListController,
    Renderer: AppointmentTypeListRenderer,
};

registry.category("views").add("appointment_type_list", AppointmentTypeListView);
