import { hrGanttView } from "@hr_gantt/hr_gantt_view";

export class AttendanceGanttRenderer extends hrGanttView.Renderer {
    static progressBarLabelTemplate = "hr_attendance.AttendanceGanttRenderer.ProgressBarLabel";
    static rowHeaderTemplate = "hr_attendance.GanttRenderer.RowHeader";

    onPillClicked(ev, pill) {
        this.props.openDialog({ resId: pill.record.id });
    }

    getProgressBarLabelStatus(progressBar) {
        const status = this.getProgressBarStatus(progressBar);
        if (status === "success") {
            return ""; // we don't want green text in this case
        }
        return `text-${status}`;
    }

    getProgressBarStatus(progressBar) {
        const { ratio } = progressBar;
        if (ratio >= 200) {
            return "danger";
        }
        if (ratio > 100) {
            return "warning";
        }
        // attendance-based employees with no attendances get a warning color
        if (ratio === 0 && progressBar.attendance_based) {
            return "warning";
        }
        return "success";
    }

    progressBarIsVisible(row) {
        return super.progressBarIsVisible(row) && !row.progressBar.is_fully_flexible_hours;
    }

    /** @override */
    processRow(row) {
        const result = super.processRow(...arguments);
        if (row.groupedByField === "employee_id" && this.model.data.employeesWithoutContractIds?.includes(row.resId)) {
            // Flag rows for employees without an active contract during the viewed period,
            // so the row header can be styled differently (e.g. displayed in red).
            for (const processedRow of result.rows) {
                processedRow.employeeHasNoContract = true;
            }
        }
        return result;
    }
}
