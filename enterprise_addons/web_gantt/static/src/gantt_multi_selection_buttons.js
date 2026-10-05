import { t, useProps } from "@odoo/owl";
import {
    MultiSelectionButtons,
    multiSelectionButtonsProps,
} from "@web/views/view_components/multi_selection_buttons";

export const ganttMultiSelectionButtonsProps = {
    reactive: t.object({
        ...multiSelectionButtonsProps.reactive.toShape(),
        onPlan: t.function().optional(),
    }),
};

export class GanttMultiSelectionButtons extends MultiSelectionButtons {
    static template = "web_gantt.GanttMultiSelectionButtons";
    props = useProps(ganttMultiSelectionButtonsProps);
}
