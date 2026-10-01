import { registry } from "@web/core/registry";
import { hrHolidaysGanttManagerHrLeaveView } from "./hr_holidays_gantt_view";
import { HrHolidaysReportSearchModel } from "./hr_holidays_report_search_model";

const viewRegistry = registry.category("views");

export const hrHolidaysReportGanttView = {
    ...hrHolidaysGanttManagerHrLeaveView,
    SearchModel: HrHolidaysReportSearchModel,
};

viewRegistry.add("hr_holidays_report_gantt", hrHolidaysReportGanttView);
