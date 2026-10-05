import { t } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import {
    GanttMultiSelectionButtons,
    ganttMultiSelectionButtonsProps,
} from "@web_gantt/gantt_multi_selection_buttons";

patch(GanttMultiSelectionButtons, { template: "sale_planning.GanttMultiSelectionButtons" });

Object.assign(ganttMultiSelectionButtonsProps.reactive.toShape(), {
    hasAvailableSOL: t.boolean().optional(),
});
