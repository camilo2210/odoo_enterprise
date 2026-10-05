import { t, useProps } from "@odoo/owl";
import { GanttRendererControls } from "@web_gantt/gantt_renderer_controls";

export class PlanningGanttRendererControls extends GanttRendererControls {
    static toolbarContentTemplate = "planning.PlanningGanttRendererControls.ToolbarContent";

    planningGanttProps = useProps({
        duplicateToolHelperReactive: t.any(),
    });
}
