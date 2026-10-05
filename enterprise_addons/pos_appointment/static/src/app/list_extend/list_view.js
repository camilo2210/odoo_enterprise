import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { PosAppointmentListController } from "./list_controller";
import { PosAppointmentListRenderer } from "./list_renderer";
import { PosAppointmentControlPanel } from "@pos_appointment/override/web/control_panel";

export const posAppointmentListView = {
    ...listView,
    Controller: PosAppointmentListController,
    Renderer: PosAppointmentListRenderer,
    ControlPanel: PosAppointmentControlPanel,
};

registry.category("views").add("pos_appointment_list", posAppointmentListView);
