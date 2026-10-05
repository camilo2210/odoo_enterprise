import { registry } from "@web/core/registry";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { Dashboard } from "../../js/dashboard/dashboard";

export class DashboardKanbanRenderer extends KanbanRenderer {
    static template = "sale_renting.DashboardKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        Dashboard,
    };
}

export const DashboardKanbanView = {
    ...kanbanView,
    Renderer: DashboardKanbanRenderer,
};

registry
    .category("views")
    .add("rental_dashboard_kanban", DashboardKanbanView);
