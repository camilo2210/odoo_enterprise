import { registry } from "@web/core/registry";

import { planningFieldServiceMapView } from "@planning_field_service/views/planning_field_service_map/planning_field_service_map_view"
import { PlanningFieldServiceLiveMapModel } from "./planning_field_service_live_map_model";
import { PlanningFieldServiceLiveMapRenderer } from "./planning_field_service_live_map_renderer";

export const planningFieldServiceLiveMapView = {
    ...planningFieldServiceMapView,
    Model: PlanningFieldServiceLiveMapModel,
    Renderer: PlanningFieldServiceLiveMapRenderer,
};

registry.category("views").add("planning_field_service_live_map", planningFieldServiceLiveMapView);
