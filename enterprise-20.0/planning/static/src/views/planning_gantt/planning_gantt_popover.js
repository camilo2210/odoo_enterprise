import { t, useProps } from "@odoo/owl";
import { GanttPopover, ganttPopoverProps } from "@web_gantt/gantt_popover";
import { usePlanningPopoverFooter } from "@planning/components/planning_popover_footer/planning_popover_footer";

// Exported so overriding modules can extend the schema: they add buttons to the
// footer template, and the props those buttons read must be declared here
// (e.g. planning_field_service adds `onStart`).
export const planningGanttPopoverProps = {
    ...ganttPopoverProps,
    onUnschedule: t.function().optional(),
    onDelete: t.function().optional(),
};

export class PlanningGanttPopover extends GanttPopover {
    static defaultFooterButtonsTemplate = "planning.PlanningGanttPopover.DefaultFooterButtons";
    props = useProps(planningGanttPopoverProps);

    setup() {
        super.setup();
        this.footer = usePlanningPopoverFooter(() => this.props.close());
    }
}
