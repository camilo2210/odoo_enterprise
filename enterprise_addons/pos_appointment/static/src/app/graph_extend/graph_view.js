import { graphView } from "@web/views/graph/graph_view";
import { registry } from "@web/core/registry";
import { PosAppointmentControlPanel } from "@pos_appointment/override/web/control_panel";

export const posAppointmentGraphView = {
    ...graphView,
    ControlPanel: PosAppointmentControlPanel,
};

registry.category("views").add("pos_appointment_graph", posAppointmentGraphView);
