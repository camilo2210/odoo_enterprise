import { posAppointmentListView } from "@pos_appointment/app/list_extend/list_view";
import { registry } from "@web/core/registry";
import { PosResAppointmentListController } from "./list_controller";
import { PosResAppointmentListRenderer } from "./list_renderer";

export const posResAppointmentListView = {
    ...posAppointmentListView,
    Controller: PosResAppointmentListController,
    Renderer: PosResAppointmentListRenderer,
};

registry.category("views").add("pos_res_appointment_list", posResAppointmentListView);
