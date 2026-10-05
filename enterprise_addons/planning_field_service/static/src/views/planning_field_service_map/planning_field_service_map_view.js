import { registry } from "@web/core/registry";
import { mapView } from "@web_map/map_view/map_view";

import { PlanningFieldServiceMapModel } from "./planning_field_service_map_model";
import { PlanningFieldServiceMapRenderer } from "./planning_field_service_map_renderer";

export const planningFieldServiceMapView = {
    ...mapView,
    Model: PlanningFieldServiceMapModel,
    Renderer: PlanningFieldServiceMapRenderer,
};

registry.category("views").add("planning_field_service_map", planningFieldServiceMapView);
