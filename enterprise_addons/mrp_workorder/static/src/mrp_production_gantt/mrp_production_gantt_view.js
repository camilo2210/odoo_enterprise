import { registry } from "@web/core/registry";
import { ganttView } from "@web_gantt/gantt_view";
import { MRPProductionGanttController } from "./mrp_production_gantt_controller";
import { MRPProductionGanttRenderer } from "./mrp_production_gantt_renderer";

const viewRegistry = registry.category("views");

export const mrpProductionGanttView = {
    ...ganttView,
    Controller: MRPProductionGanttController,
    Renderer: MRPProductionGanttRenderer,
};

viewRegistry.add("mrp_production_gantt", mrpProductionGanttView);
