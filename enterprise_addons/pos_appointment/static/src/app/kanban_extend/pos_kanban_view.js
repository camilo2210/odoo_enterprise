import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { PosKanbanRenderer } from "./kanban_renderer";
import { PosKanbanController } from "./kanban_controller";
import { PosAppointmentControlPanel } from "@pos_appointment/override/web/control_panel";

export const posKanbanView = {
    ...kanbanView,
    Renderer: PosKanbanRenderer,
    Controller: PosKanbanController,
    ControlPanel: PosAppointmentControlPanel,
};

registry.category("views").add("pos_kanban", posKanbanView);
