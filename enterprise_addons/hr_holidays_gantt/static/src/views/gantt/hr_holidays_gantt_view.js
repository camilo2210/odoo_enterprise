import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { registry } from "@web/core/registry";
import { HrHolidaysGanttController } from "./hr_holidays_gantt_controller";
import { HrHolidaysGanttModel } from "./hr_holidays_gantt_model";
import { HrHolidaysGanttSearchModel } from "./hr_holidays_gantt_search_model";
import { HrHolidaysGanttRenderer } from "./hr_holidays_gantt_renderer";

const viewRegistry = registry.category("views");

export const hrHolidaysGanttManagerHrLeaveView = {
    ...hrGanttView,
    Controller: HrHolidaysGanttController,
    Renderer: HrHolidaysGanttRenderer,
    Model: HrHolidaysGanttModel,
    SearchModel: HrHolidaysGanttSearchModel,
    buttonTemplate: "hr_holidays_gantt.GanttView.Buttons",
};

viewRegistry.add("hr_holidays_gantt_manager_hr_leave", hrHolidaysGanttManagerHrLeaveView);
