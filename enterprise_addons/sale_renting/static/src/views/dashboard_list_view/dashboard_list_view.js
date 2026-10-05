import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";
import { Dashboard } from "../../js/dashboard/dashboard";

export class DashboardListRenderer extends ListRenderer {
    static template = "sale_renting.DashboardListRenderer";
    static components = {
        ...ListRenderer.components,
        Dashboard,
    };
}

export const DashboardListView = {
    ...listView,
    Renderer: DashboardListRenderer,
};

registry.category("views").add("rental_dashboard_list", DashboardListView);
