import { registry } from "@web/core/registry";
import { MonthlyAttendanceGanttRenderer } from "./monthly_attendance_gantt_renderer";
import { attendanceGanttView } from "./attendance_gantt_view";

export const monthlyAttendanceGanttView = {
    ...attendanceGanttView,
    Renderer: MonthlyAttendanceGanttRenderer,
};

registry.category("views").add("monthly_attendance_gantt", monthlyAttendanceGanttView);
