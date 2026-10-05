import { useService } from "@web/core/utils/hooks";
import { deserializeDate } from "@web/core/l10n/dates";
import { session } from "@web/session";

import { TimesheetGridRenderer } from "../timesheet_grid/timesheet_grid_renderer";

export class TimesheetGridMyTimesheetsRenderer extends TimesheetGridRenderer {
    static subTemplates = {
        ...TimesheetGridRenderer.subTemplates,
        barChart: "timesheet_grid.TimesheetGridMyTimesheetsTotal",
    };

    setup() {
        super.setup();
        this.timesheetUOMService = useService("timesheet_uom");
        this.lastValidatedTimesheetDate = false;
    }

    /**
     * Format the overtime to display it in the total of the column
     *
     * @param {number} dailyOvertime
     * @returns {string|string}
     */
    formatDailyOvertime(dailyOvertime) {
        return dailyOvertime
            ? `${dailyOvertime > 0 ? "+" : ""}${this.formatValue(dailyOvertime)}`
            : "";
    }

    /**
     * Compute the overtime for a particular column
     *
     * @param {import("@web_grid/views/grid_model").DateGridColumn} column
     * @returns {number|null} overtime for that particular day
     */
    getDailyOvertime(column) {
        if (!Object.keys(this.props.model.workingHoursData.daily).length) {
            return null;
        }
        let overtime = 0;
        if (column.value in this.props.model.workingHoursData.daily) {
            const workingHours = this.props.model.workingHoursData.daily[column.value];
            overtime = column.grandTotal - workingHours;
        }
        return overtime;
    }

    getColumnTotalClassNames(column) {
        const daily = this.props.model.workingHoursData.daily;
        if (
            ("full_time_required_hours" in daily && daily[column.value] === 0) ||
            !(column.value in daily)
        ) {
            return "";
        }

        const dailyOvertime = this.getDailyOvertime(column);
        if (dailyOvertime >= 0 || this.getUnavailableClass(column) === "o_grid_unavailable") {
            return "text-success";
        } else if (dailyOvertime < 0) {
            return "text-danger";
        }
    }

    /**
     * Format the overtime to display it in the total of the weekly summary column
     *
     * @param {number} weeklyOvertime
     * @returns {string|string}
     */
    formatWeeklyOvertime(weeklyOvertime) {
        return weeklyOvertime
            ? `${weeklyOvertime > 0 ? "+" : ""}${this.formatValue(weeklyOvertime)}`
            : "";
    }

    /**
     * Compute the overtime for the week
     *
     * @returns {number|null} overtime for the week
     */
    getWeeklyOvertime() {
        if (!Object.keys(this.props.model.workingHoursData.daily).length) {
            return null;
        }
        if ("full_time_required_hours" in this.props.model.workingHoursData.daily) {
            const grandTotal = this.props.model.columnsArray.reduce(
                (total, column) => total + column.grandTotal,
                0
            );
            return grandTotal - this.props.model.workingHoursData.daily.full_time_required_hours;
        }
        return this.props.model.columnsArray.reduce(
            (overtime, column) => overtime + this.getDailyOvertime(column),
            0
        );
    }

    getFooterTotalCellClasses(grandTotal) {
        const weeklyOvertime = this.getWeeklyOvertime();
        if (weeklyOvertime == null) {
            return super.getFooterTotalCellClasses(grandTotal);
        } else if (weeklyOvertime >= 0) {
            return "border-success bg-success-subtle text-success";
        } else {
            return "border-danger bg-danger-subtle text-danger";
        }
    }

    async _getLastValidatedTimesheetDate(props = this.props) {
        const res = await props.model.orm.call("res.users", "get_last_validated_timesheet_date", [
            session.user_id,
        ]);
        this.lastValidatedTimesheetDate = res && deserializeDate(res);
    }

    getDisplayAddLine(row) {
        return (
            super.getDisplayAddLine(row) &&
            (!this.lastValidatedTimesheetDate ||
                this.lastValidatedTimesheetDate.startOf("day") <
                    this.props.model.navigationInfo.periodEnd.startOf("day"))
        );
    }
}
