import { planningGanttView } from "@planning/views/planning_gantt/planning_gantt_view";

import { MapTimelineGanttModel } from "./planning_field_service_map_timeline_gantt_model";
import { MapTimelineGanttRenderer } from "./planning_field_service_map_timeline_gantt_renderer";

export const planningFieldServiceMapTimelineGanttView = {
    ...planningGanttView,
    Model: MapTimelineGanttModel,
    Renderer: MapTimelineGanttRenderer,
};
