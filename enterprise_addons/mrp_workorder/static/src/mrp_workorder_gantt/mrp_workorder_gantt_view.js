import { ganttView } from "@web_gantt/gantt_view";
import { MRPWorkorderGanttController } from "./mrp_workorder_gantt_controller";
import { MRPWorkorderGanttRenderer } from "./mrp_workorder_gantt_renderer";
import { MRPWorkorderGanttArchParser } from "./mrp_workorder_gantt_arch_parser";
import { registry } from "@web/core/registry";

const viewRegistry = registry.category("views");

export const mrpWorkorderGanttView = {
    ...ganttView,
    ArchParser: MRPWorkorderGanttArchParser,
    Controller: MRPWorkorderGanttController,
    Renderer: MRPWorkorderGanttRenderer,
    buttonTemplate: "mrp_workorder.MRPWorkorderGanttView.Buttons",
};

viewRegistry.add("mrp_workorder_gantt", mrpWorkorderGanttView);
