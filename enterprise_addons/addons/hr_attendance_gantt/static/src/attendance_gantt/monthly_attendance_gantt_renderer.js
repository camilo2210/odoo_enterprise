import { serializeDateTime } from "@web/core/l10n/dates";
import { AttendanceCalendarOverview } from "@hr_attendance/components/attendance_calendar/attendance_calendar_overview";
import { AttendanceGanttRenderer } from "./attendance_gantt_renderer";

export class MonthlyAttendanceGanttRenderer extends AttendanceGanttRenderer {
    static template = "hr_attendance_gantt.MonthlyAttendanceGanttRenderer";
    static components = {
        ...AttendanceGanttRenderer.components,
        AttendanceCalendarOverview,
    };

    get dateRange() {
        const { startDate, stopDate } = this.model.metaData;
        return {
            start: serializeDateTime(startDate),
            end: serializeDateTime(stopDate.endOf("day")),
        };
    }
}
