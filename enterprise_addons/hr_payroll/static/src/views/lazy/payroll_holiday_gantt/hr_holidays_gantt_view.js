import { registry } from "@web/core/registry";
import { hrHolidaysGanttManagerHrLeaveView } from "@hr_holidays_gantt/views/gantt/hr_holidays_gantt_view";
import { PayrollHolidaysGanttRenderer } from "./payroll_holidays_gantt_renderer";

export const hrPayrollHolidaysGanttView = {
    ...hrHolidaysGanttManagerHrLeaveView,
    Renderer: PayrollHolidaysGanttRenderer,
};

registry.category("views").add("hr_payroll_holidays_gantt_manager", hrPayrollHolidaysGanttView);