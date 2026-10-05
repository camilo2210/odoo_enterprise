import { serializeDate } from "@web/core/l10n/dates";
import { TimesheetGridModel } from "../timesheet_grid/timesheet_grid_model";
import { user } from "@web/core/user";

export class TimesheetGridMyTimesheetsModel extends TimesheetGridModel {
    setup(params, services) {
        super.setup(params, services);
        this.fieldsInfo.project_id.required = "True";
    }

    getTimesheetWorkingHoursPromises(metaData) {
        const promises = super.getTimesheetWorkingHoursPromises(metaData);
        promises.push(this._fetchDailyWorkingHours(metaData));
        return promises;
    }

    async _fetchDailyWorkingHours({ data }) {
        const { periodStart, periodEnd } = this.navigationInfo;
        const dailyWorkingHours = await this.orm.call("res.users", "get_daily_working_hours", [
            user.userId,
            serializeDate(periodStart),
            serializeDate(periodEnd),
        ]);
        data.workingHours.daily = dailyWorkingHours;
    }

    async _getInitialData(metaData) {
        const initialData = await super._getInitialData(metaData);
        const { data } = initialData;
        data.workingHours.daily = {};
        return initialData;
    }

    async _fetchUnavailabilityDays(metaData, args = {}) {
        return super._fetchUnavailabilityDays(metaData, {
            context: { get_current_user_unavailable_dates: true },
            ...args,
        });
    }
}
