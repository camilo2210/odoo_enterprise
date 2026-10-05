import { registry } from "@web/core/registry";

import { planningFieldServiceMapView } from "@planning_field_service/views/planning_field_service_map/planning_field_service_map_view";

import { PlanningFieldServiceMapTimelineController } from "./planning_field_service_map_timeline_controller";
import { PlanningFieldServiceMapTimelineModel } from "./planning_field_service_map_timeline_model";
import { PlanningFieldServiceMapTimelineRenderer } from "./planning_field_service_map_timeline_renderer";

export const planningFieldServiceMapTimelineView = {
    ...planningFieldServiceMapView,
    Controller: PlanningFieldServiceMapTimelineController,
    Model: PlanningFieldServiceMapTimelineModel,
    Renderer: PlanningFieldServiceMapTimelineRenderer,
    buttonTemplate: "planning_field_service.MapTimelineView.Buttons",
};

registry
    .category("views")
    .add("planning_field_service_map_timeline", planningFieldServiceMapTimelineView);
