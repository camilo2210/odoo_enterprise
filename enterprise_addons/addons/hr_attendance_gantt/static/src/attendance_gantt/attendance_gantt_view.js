import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { registry } from "@web/core/registry";
import { AttendanceGanttModel } from "./attendance_gantt_model";
import { AttendanceGanttRenderer } from "./attendance_gantt_renderer";
import { AttendanceGanttSearchModel } from "./attendance_gantt_search_model";
import { AttendanceActionHelper } from "@hr_attendance/views/attendance_helper_view";

export class AttendanceGanttController extends hrGanttView.Controller {
    static template = "hr_attendance.AttendanceGanttController";
    static components = {
        ...hrGanttView.Controller.components,
        AttendanceActionHelper,
    }

    get showNoContentHelp() {
        // Show if first row is empty (means no records)
        return this.model.data.rows.length < 2 && this.model.data.rows[0].recordIds.length === 0;
    }
}
const viewRegistry = registry.category("views");

export const attendanceGanttView = {
    ...hrGanttView,
    Controller: AttendanceGanttController,
    Model: AttendanceGanttModel,
    Renderer: AttendanceGanttRenderer,
    SearchModel: AttendanceGanttSearchModel,
};

viewRegistry.add("attendance_gantt", attendanceGanttView);
