import { t } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

import {
    PlanningGanttPopover,
    planningGanttPopoverProps,
} from "@planning/views/planning_gantt/planning_gantt_popover";

// this module's own footer template extension adds "Start"/"Complete" buttons reading these props
Object.assign(planningGanttPopoverProps, {
    onStart: t.function().optional(),
    onComplete: t.function().optional(),
    onNavigate: t.function().optional(),
});

patch(PlanningGanttPopover.prototype, {
    get readonly() {
        const record = this.props.model.data.records.find((rec) => rec.id === this.props.resId);
        return !record?.can_edit;
    },
});
