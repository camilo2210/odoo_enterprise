import { t, usePlugin, useProps } from "@odoo/owl";
import { ganttControllerProps } from "@web_gantt/gantt_controller";

import { PlanningGanttController } from "@planning/views/planning_gantt/planning_gantt_controller";

import { MapTimelineCommunicationPlugin } from "../map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";

export class MapTimelineGanttController extends PlanningGanttController {
    static template = "planning_field_service.MapTimelineGanttView";

    props = useProps({
        ...ganttControllerProps,
        contentRef: t.any().optional(),
    });

    communication = usePlugin(MapTimelineCommunicationPlugin);

    setup() {
        super.setup(...arguments);
        this.communication.onFoldedGroupsChange(() => this.model.notify());
    }
}
