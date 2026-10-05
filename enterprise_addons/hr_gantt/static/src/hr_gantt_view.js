import { ganttView } from "@web_gantt/gantt_view";
import { HrGanttRenderer } from "./hr_gantt_renderer";
import { registry } from "@web/core/registry";
import { HrGanttModel } from "./hr_gantt_model";

const viewRegistry = registry.category("views");

export const hrGanttView = {
    ...ganttView,
    Model: HrGanttModel,
    Renderer: HrGanttRenderer,
    searchMenuTypes: ["filter", "groupBy", "favorite"],
};

viewRegistry.add("hr_gantt", hrGanttView);
